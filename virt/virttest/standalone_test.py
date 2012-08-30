import os, logging, imp, sys, time, traceback
from autotest.client.shared import error
import utils_misc, env_process


_root_path = os.path.join(sys.modules[__name__].__file__, "..", "..")
ROOT_PATH = os.path.abspath(_root_path)


class Test(object):
    """
    Mininal test class used to run a virt test.
    """
    env_version = 1
    def __init__(self, params):
        self.params = params
        self.bindir = ROOT_PATH
        self.testdir = os.path.join(self.bindir, 'tests')
        self.virtdir = os.path.join(self.bindir, 'shared')

        self.srcdir = os.path.join(self.bindir, params.get('vm_type'), 'src')
        if not os.path.isdir(self.srcdir):
            os.makedirs(self.srcdir)

        self.tmpdir = os.path.join(self.bindir, 'tmp')
        if not os.path.isdir(self.tmpdir):
            os.makedirs(self.tmpdir)

        self.iteration = 0
        self.tag = ("%s.%s" %
                    (params.get("vm_type"), params.get("shortname")))
        self.debugdir = None
        self.outputdir = None
        self.logfile = None
        self.file_handler = None


    def set_debugdir(self, debugdir):
        self.debugdir = os.path.join(debugdir, self.tag)
        self.outputdir = self.debugdir
        if not os.path.isdir(self.debugdir):
            os.makedirs(self.debugdir)
        utils_misc.set_log_file_dir(self.debugdir)
        self.logfile = os.path.join(self.debugdir, 'debug.log')


    def write_test_keyval(self, d):
        logging.debug(d)


    def start_file_logging(self):
        self.file_handler = configure_file_logging(self.logfile)


    def stop_file_logging(self):
        logger = logging.getLogger()
        logger.removeHandler(self.file_handler)


    def run_once(self):
        self.start_file_logging()
        # Convert params to a Params object
        params = utils_misc.Params(self.params)

        # If a dependency test prior to this test has failed, let's fail
        # it right away as TestNA.
        if params.get("dependency_failed") == 'yes':
            raise error.TestNAError("Test dependency failed")

        # Report the parameters we've received and write them as keyvals
        logging.debug("Test parameters:")
        keys = params.keys()
        keys.sort()
        for key in keys:
            logging.debug("    %s = %s", key, params[key])

        # Open the environment file
        env_filename = os.path.join(self.bindir, params.get("vm_type"),
                                    params.get("env", "env"))
        env = utils_misc.Env(env_filename, self.env_version)

        test_passed = False

        try:
            try:
                try:
                    subtest_dirs = []
                    tests_dir = self.testdir

                    other_subtests_dirs = params.get("other_tests_dirs", "")
                    for d in other_subtests_dirs.split():
                        subtestdir = os.path.join(tests_dir, d, "tests")
                        if not os.path.isdir(subtestdir):
                            raise error.TestError("Directory %s does not "
                                                  "exist" % (subtestdir))
                        subtest_dirs.append(subtestdir)

                    # Verify if we have the correspondent source file for it
                    subtest_dirs.append(self.testdir)
                    specific_testdir = os.path.join(self.bindir,
                                                    params.get("vm_type"),
                                                    "tests")
                    subtest_dirs.append(specific_testdir)
                    subtest_dir = None

                    # Get the test routine corresponding to the specified
                    # test type
                    t_types = params.get("type").split()
                    test_modules = {}
                    for t_type in t_types:
                        for d in subtest_dirs:
                            module_path = os.path.join(d, "%s.py" % t_type)
                            if os.path.isfile(module_path):
                                subtest_dir = d
                                break
                        if subtest_dir is None:
                            msg = ("Could not find test file %s.py on test"
                                   "dirs %s" % (t_type, subtest_dirs))
                            raise error.TestError(msg)
                        # Load the test module
                        f, p, d = imp.find_module(t_type, [subtest_dir])
                        test_modules[t_type] = imp.load_module(t_type, f, p, d)
                        f.close()

                    # Preprocess
                    try:
                        env_process.preprocess(self, params, env)
                    finally:
                        env.save()

                    # Run the test function
                    for t_type, test_module in test_modules.items():
                        run_func = getattr(test_module, "run_%s" % t_type)
                        try:
                            run_func(self, params, env)
                        finally:
                            env.save()
                    test_passed = True

                except Exception, e:
                    logging.error("Test failed: %s: %s",
                                  e.__class__.__name__, e)
                    try:
                        env_process.postprocess_on_error(self, params, env)
                    finally:
                        env.save()
                    raise

            finally:
                # Postprocess
                try:
                    try:
                        env_process.postprocess(self, params, env)
                    except Exception, e:
                        if test_passed:
                            raise
                        logging.error("Exception raised during "
                                      "postprocessing: %s", e)
                finally:
                    env.save()

        except Exception, e:
            if params.get("abort_on_error") != "yes":
                raise
            # Abort on error
            logging.info("Aborting job (%s)", e)
            if params.get("vm_type") == "kvm":
                for vm in env.get_all_vms():
                    if vm.is_dead():
                        continue
                    logging.info("VM '%s' is alive.", vm.name)
                    for m in vm.monitors:
                        logging.info("It has a %s monitor unix socket at: %s",
                                     vm.name, m.protocol, m.filename)
                    logging.info("The command line used to start it was:\n%s",
                                 vm.name, vm.make_qemu_command())
                raise error.JobError("Abort requested (%s)" % e)

        self.stop_file_logging()

        return test_passed


def configure_logging():
    """
    Remove all the handlers on the root logger
    """
    logger = logging.getLogger()
    for hdlr in logger.handlers:
        logger.removeHandler(hdlr)


def configure_console_logging():
    """
    Simple helper for adding a file logger to the root logger.
    """
    logger = logging.getLogger()
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG)

    fmt = '%(asctime)s %(levelname)-5.5s| %(message)s'
    formatter = logging.Formatter(fmt=fmt, datefmt='%H:%M:%S')

    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return stream_handler


def configure_file_logging(logfile):
    """
    Simple helper for adding a file logger to the root logger.
    """
    logger = logging.getLogger()
    file_handler = logging.FileHandler(filename=logfile)
    file_handler.setLevel(logging.DEBUG)

    fmt = '%(asctime)s %(levelname)-5.5s| %(message)s'
    formatter = logging.Formatter(fmt=fmt, datefmt='%H:%M:%S')

    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return file_handler


def run_tests(parser):
    """
    Runs the sequence of KVM tests based on the list of dctionaries
    generated by the configuration system, handling dependencies.

    @param parser: Config parser object.
    @return: True, if all tests ran passed, False if any of them failed.
    """
    debugdir = os.path.join(ROOT_PATH, 'logs',
                            'run-%s' % time.strftime('%Y-%m-%d-%H.%M.%S'))
    if not os.path.isdir(debugdir):
        os.makedirs(debugdir)
    debuglog = os.path.join(debugdir, "debug.log")
    configure_file_logging(debuglog)

    last_index = -1
    for i, d in enumerate(parser.get_dicts()):
        logging.info("Test %4d:  %s" % (i + 1, d["shortname"]))
        last_index += 1

    status_dct = {}
    failed = False
    # Add the parameter decide if setup host env in the test case
    # For some special tests we only setup host in the first and last case
    # When we need to setup host env we need the host_setup_flag as following:
    #    0(00): do nothing
    #    1(01): setup env
    #    2(10): cleanup env
    #    3(11): setup and cleanup env
    index = 0
    setup_flag = 1
    cleanup_flag = 2
    for dct in parser.get_dicts():

        if index == 0:
            if dct.get("host_setup_flag", None) is not None:
                flag = int(dct["host_setup_flag"])
                dct["host_setup_flag"] = flag | setup_flag
            else:
                dct["host_setup_flag"] = setup_flag
        if index == last_index:
            if dct.get("host_setup_flag", None) is not None:
                flag = int(dct["host_setup_flag"])
                dct["host_setup_flag"] = flag | cleanup_flag
            else:
                dct["host_setup_flag"] = cleanup_flag
        index += 1

        # Add kvm module status
        dct["kvm_default"] = utils_misc.get_module_params(
                                             dct.get("sysfs_dir", "sys"), "kvm")

        if dct.get("skip") == "yes":
            continue

        dependencies_satisfied = True
        for dep in dct.get("dep"):
            for test_name in status_dct.keys():
                if not dep in test_name:
                    continue
                # So the only really non-fatal state is WARN,
                # All the others make it not safe to proceed
                if status_dct[test_name] not in ['GOOD', 'WARN']:
                    dependencies_satisfied = False
                    break

        current_status = False
        if dependencies_satisfied:
            t = Test(dct)
            t.set_debugdir(debugdir)

            sys.stdout.switch()
            print("%s:" % t.tag),
            sys.stdout.switch()

            try:
                current_status = t.run_once()
            except:
                traceback.print_exc()
                current_status = False

        if not current_status:
            failed = True
            sys.stdout.switch()
            print("FAIL")
            sys.stdout.switch()

        else:
            sys.stdout.switch()
            print("PASS")
            sys.stdout.switch()

        status_dct[dct.get("name")] = current_status

    return not failed