/*
 * (C) Copyright IBM Corp. 2004, 2005
 *
 * This program is free software; you can redistribute it and/or modify it
 * under the terms and conditions of the GNU General Public License,
 * version 2, as published by the Free Software Foundation.
 *
 * This program is distributed in the hope it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 * FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
 * more details.
 *
 * You should have received a copy of the GNU General Public License along with
 * this program; if not, write to the Free Software Foundation, Inc., 59 Temple
 * Place - Suite 330, Boston, MA 02111-1307 USA.
 *
 * Authors:
 *     Carl McAdams <carlmc@us.ibm.com>
 *
 * Spec:        HPI-B.01.01
 * Function:    saHpiEventLogEntryAdd
 * Description:   
 *   For Event logs which support OVERFLOW_DROP overflow action,  
 *   add entries until the overflow is exceeded.
 *   saHpiEventLogEntryAdd() returns SA_OK, and the number of entries
 *   is not greater than the size. 
 * Line:        P52-1:P52-10
 *
 */
#include <stdio.h>
#include <string.h>
#include "saf_test.h"

#define TEST_STRING     "Event Test"
#define TEST_STRING_LENGTH 10

int overflow_test(SaHpiSessionIdT session, SaHpiResourceIdT resourceId)
{
	SaHpiEventLogInfoT info;
	SaErrorT status;
	SaHpiUint32T index, size;
	SaHpiEventT testevent;
	//SaHpiEventLogEntryIdT   PrevEntryId, NextEntryId;
	//SaHpiEventLogEntryT     EventLogEntry;
	int retval = SAF_TEST_UNKNOWN;
	SaHpiBoolT LogFilled = SAHPI_FALSE;

	status = saHpiEventLogInfoGet(session, resourceId, &info);
	if (status != SA_OK) {
		e_print(saHpiEventLogInfoGet, SA_OK, status);
		retval = SAF_TEST_UNRESOLVED;
	} else {
		size = info.Size;
		//Event log exist, but is always empty 
		if ((size == 0) ||
		    (info.OverflowAction != SAHPI_EL_OVERFLOW_DROP)) {
			// If the size is not real or if the overflow
			// behavior is not fitting for this test, 
			// then just pass this resource or domain.
			retval = SAF_TEST_NOTSUPPORT;
		}
	}

	// Clear the eventlog
	if (retval == SAF_TEST_UNKNOWN) {
		// Not only should this clear the event log,
		// but the overflow flag should be reset.
		status = saHpiEventLogClear(session, resourceId);
		if (status != SA_OK) {
			// return a bad status if unable to clear.
			e_print(saHpiEventLogClear, SA_OK, status);
			retval = SAF_TEST_UNRESOLVED;
		}
	}
	// Create the first entry in the eventlog
	if (retval == SAF_TEST_UNKNOWN) {
		testevent.EventType = SAHPI_ET_USER;
		testevent.Source = SAHPI_UNSPECIFIED_RESOURCE_ID;
		testevent.Timestamp = SAHPI_TIME_UNSPECIFIED;
		testevent.Severity = SAHPI_INFORMATIONAL;
		strncpy(testevent.EventDataUnion.UserEvent.UserEventData.Data,
			TEST_STRING, TEST_STRING_LENGTH);
		testevent.EventDataUnion.UserEvent.UserEventData.DataLength =
		    TEST_STRING_LENGTH;
		testevent.EventDataUnion.UserEvent.UserEventData.Language =
		    SAHPI_LANG_ENGLISH;
		testevent.EventDataUnion.UserEvent.UserEventData.DataType =
		    SAHPI_TL_TYPE_TEXT;

		status = saHpiEventLogEntryAdd(session, resourceId, &testevent);
		if (status != SA_OK) {
			e_print(saHpiEventLogEntryAdd, SA_OK, status);
			retval = SAF_TEST_UNRESOLVED;
		}
	}
	// Fill up the rest of the eventlog
	if (retval == SAF_TEST_UNKNOWN) {
		testevent.Severity = SAHPI_OK;
		for (index = 1; index < info.Size; index++) {
			status = saHpiEventLogEntryAdd(session,
						       resourceId, &testevent);
			if (status != SA_OK) {
				e_print(saHpiEventLogEntryAdd, SA_OK, status);
				retval = SAF_TEST_UNRESOLVED;
				break;
			}
		}
	}
	// test to make sure the eventlog is full
	if (retval == SAF_TEST_UNKNOWN) {

		status = saHpiEventLogInfoGet(session, resourceId, &info);
		if (status != SA_OK) {
			e_print(saHpiEventLogInfoGet, SA_OK, status);
			retval = SAF_TEST_UNRESOLVED;
		} else {
			if (info.Entries != info.Size) {
				printf("  EventLog was not filled up!\n");
				retval = SAF_TEST_UNRESOLVED;
			}
		}
	}
	// Add another entry to overflow the maximum limit
	if (retval == SAF_TEST_UNKNOWN) {
		testevent.Severity = SAHPI_INFORMATIONAL;
		status = saHpiEventLogEntryAdd(session, resourceId, &testevent);
		if (status != SA_ERR_HPI_OUT_OF_SPACE) {
			e_print(saHpiEventLogEntryAdd,
				SA_ERR_HPI_OUT_OF_SPACE, status);
			retval = SAF_TEST_FAIL;
		}
	}
	// Get the last entry
	if (retval == SAF_TEST_UNKNOWN) {
		status = saHpiEventLogInfoGet(session, resourceId, &info);
		if (status != SA_OK) {
			e_print(saHpiEventLogInfoGet, SA_OK, status);
			retval = SAF_TEST_UNRESOLVED;
		}
	}
	// Compare last entry to make sure our overflow attempt did overwrite
	if (retval == SAF_TEST_UNKNOWN) {
		if (info.Entries > info.Size) {
			// This event should have been set to a different severity.
			printf
			    ("  \"saHpiEventLogInfoAdd\" does not conform to expected behavior\n");
			printf
			    ("  The number of event log entries exceeded the size!\n");
			retval = SAF_TEST_FAIL;
		} else {
			//The overflow attempt overwritten the oldest entry as expected.
			retval = SAF_TEST_PASS;
		}
	}
	// clean up
	if (LogFilled != SAHPI_FALSE)
		status = saHpiEventLogClear(session, resourceId);
	return retval;
}

int testcase_domain(SaHpiSessionIdT session)
{
	int retval = SAF_TEST_UNKNOWN;

	// Test the domain event log
	retval = overflow_test(session, SAHPI_UNSPECIFIED_RESOURCE_ID);

	return retval;
}

int Test_Resource(SaHpiSessionIdT session,
		  SaHpiRptEntryT report, callback2_t func)
{
	int retval = SAF_TEST_UNKNOWN;

	if (report.ResourceCapabilities & SAHPI_CAPABILITY_EVENT_LOG)
		retval = overflow_test(session, report.ResourceId);
	else {
		//Resource does not support Event logs
		retval = SAF_TEST_NOTSUPPORT;
	}
	return retval;
}

int main()
{
	int retval = SAF_TEST_UNKNOWN;

	retval = process_all_domains(Test_Resource, NULL, testcase_domain);

	return retval;
}
