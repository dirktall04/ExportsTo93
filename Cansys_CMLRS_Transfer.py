#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Cansys_CMLRS_Transfer.py
# Created by Dirktall04 on 2015-12-07
# Modified by Dirktall04 on 2015-12-31

print "Script starting."

import os
import sys
import datetime

from export_to_93_config import sdeCMLRS, gdb_93_CMLRS, pythonLogTable, metadataTempFolder

gdbCMLRSLocation = os.path.split(gdb_93_CMLRS)[:-1][0]
gdbCMLRSTable = os.path.split(gdb_93_CMLRS)[-1]

print "gdbCMLRSLocation = " + str(gdbCMLRSLocation)
print "gdbCMLRSTable = " + gdbCMLRSTable

#gdbCMLRSLocation = r"\\dt00mh02\Planning\Cart\projects\Sharedfor93\SharedSDEProd.gdb"
#gdbCMLRSTable = r"SHARED_CANSYS_CMLRS"
#pythonLogTable = r"C:\GIS\Python\ExportsTo93\geo@countyMaps.sde\countyMaps.SDE.pythonLogging"
#metadataTempFolder = r"C:\GIS\metatemp"


print "Starting imports from dt_logging."

try:
    from KDOT_Imports.dt_logging import scriptSuccess  # @UnresolvedImport
except:
    print "Failed to import scriptSuccess"

try:
    from KDOT_Imports.dt_logging import scriptFailure  # @UnresolvedImport
except:
    print "Failed to import scriptFailure"

try:
    from KDOT_Imports.dt_logging import ScriptStatusLogging  # @UnresolvedImport
except:
    print "Failed to import from KDOT_Imports.dt_logging"
    scriptSuccess = ""
    scriptFailure = ""
    def ScriptStatusLogging(taskName = 'Unavailable', taskTarget = 'Unknown',
                        completionStatus = scriptFailure, taskStartDateTime = datetime.datetime.now(), 
                        taskEndDateTime = datetime.datetime.now(), completionMessage = 'Unexpected Error.',
                        tableForLogs = pythonLogTable):
        print "ScriptStatusLogging import failed."

print "Trying to import arcpy functions."

#import arcpy functions used in this script
from arcpy import (ClearWorkspaceCache_management,
                Delete_management, Describe, env, Exists, MetadataImporter_conversion,
                FeatureClassToFeatureClass_conversion, 
                TruncateTable_management, XSLTransform_conversion)
from arcpy.da import (InsertCursor as daInsertCursor, SearchCursor as daSearchCursor)  # @UnresolvedImport

print "Completed import of arcpy functions."

env.overwriteOutput = True
in_memory = "in_memory"
##lambertCC = "PROJCS['NAD_83_Kansas_Lambert_Conformal_Conic_Meters',GEOGCS['GCS_North_American_1983',DATUM['D_North_American_1983',SPHEROID['GRS_1980',6378137.0,298.257222101]],PRIMEM['Greenwich',0.0],UNIT['Degree',0.0174532925199433]],PROJECTION['Lambert_Conformal_Conic'],PARAMETER['false_easting',0.0],PARAMETER['false_northing',0.0],PARAMETER['central_meridian',-98.0],PARAMETER['standard_parallel_1',38.0],PARAMETER['standard_parallel_2',39.0],PARAMETER['scale_factor',1.0],PARAMETER['latitude_of_origin',38.5],UNIT['Meter',1.0]]"


def RemoveGpHistory_fc(out_xml_dir):
    remove_gp_history_xslt = r"C:\GIS\metadataremoval\removeGeoprocessingHistory.xslt"
    print "Trying to remove out_xml_dir/metadtaTempFolder..."
    if Exists(out_xml_dir):
        Delete_management(out_xml_dir)
    else:
        pass
    os.mkdir(out_xml_dir)
    env.workspace = out_xml_dir
    ClearWorkspaceCache_management()
    
    try:
        print "Starting xml conversion."
        name_xml = "CMLRS_LAM.xml"
        #Process: XSLT Transformation
        XSLTransform_conversion(gdb_93_CMLRS, remove_gp_history_xslt, name_xml, "")
        print("Completed xml conversion on %s") % (gdb_93_CMLRS)
        # Process: Metadata Importer
        MetadataImporter_conversion(name_xml, gdb_93_CMLRS)
    except:
        print("Could not complete xml conversion on %s") % (gdb_93_CMLRS)
        endTime = datetime.datetime.now()
        ScriptStatusLogging('Cansys_CMLRS_Transfer', 'SharedSDEProd.gdb\SHARED_CANSYS_CMLRS',
            scriptFailure, startTime, endTime, "Could not complete xml conversion on " + gdb_93_CMLRS,
            pythonLogTable)
        
        # Reraise the error to stop execution and prevent a success message
        # from being inserted into the table.
        raise


def transferFeatures():
    env.workspace = in_memory
    featuresToTransfer = list()
    try:
        # Create an in_memory feature class which to hold the features from
        # the Oracle table.
        FeatureClassToFeatureClass_conversion(sdeCMLRS,"in_memory","CMLRS")
        
        #truncating CDRS segments in KanDrive Spatial
        print str(datetime.datetime.now()) + " truncating CMLRS segments in KanDrive Spatial."
        env.workspace = gdbCMLRSLocation
        TruncateTable_management(gdbCMLRSTable)
        env.workspace = in_memory
        
        ###############################################################################################################
        # Maintainability information:
        # If you need to add another field to transfer between the two, just add it to both of the
        # tables and give it the same name in both.
        ###############################################################################################################
        
        # searchCursorFields go to r"in_memory\CMLRS". (Input table)(Indirect)
        Sde_CMLRS_Object = Describe(r"in_memory\CMLRS")
        Sde_CMLRS_Fields = [field.name for field in Sde_CMLRS_Object.fields]
        Gdb_CMLRS_Object = Describe(gdb_93_CMLRS)
        Gdb_CMLRS_Fields = [field.name for field in Gdb_CMLRS_Object.fields]
        
        # This Python list comprehension creates the intersection of the two *_Fields lists
        # and makes sure that the Shape field and Object ID fields are not directly
        # transfered. -- The 'SHAPE@' token indirectly transfers the geometry instead
        # and the Object ID of the target feature class is automatically calculated
        # by the insert cursor.
        searchCursorFields = [fieldName for fieldName in Sde_CMLRS_Fields if 
                              fieldName in Gdb_CMLRS_Fields and
                              fieldName != Sde_CMLRS_Object.OIDFieldName and
                              fieldName != Gdb_CMLRS_Object.OIDFieldName and
                              fieldName != 'Shape']
        
        searchCursorFields.append('SHAPE@')
        
        # Make the insertCursor use the same fields as the searchCursor.
        insertCursorFields = searchCursorFields
        
        print "fieldNames to be used in the searchCursor (and insertCursor):"
        for fieldName in searchCursorFields:
            print fieldName        
        
        CMLRS_SearchCursor = daSearchCursor(r"in_memory\CMLRS", searchCursorFields)
        
        for CMLRS_CursorItem in CMLRS_SearchCursor:
            featureItem = list(CMLRS_CursorItem)
            featuresToTransfer.append(featureItem)
        
        CMLRS_InsertCursor = daInsertCursor(gdb_93_CMLRS, insertCursorFields)
        
        for CMLRS_Feature in featuresToTransfer:
            insertOID = CMLRS_InsertCursor.insertRow(CMLRS_Feature)
            print "Inserted a row with the OID of: " + str(insertOID)
        
    
    except:
        print "An error occurred."
        errorItem = sys.exc_info()[1]
        errorStatement = str(errorItem.args[0])
        print errorStatement
        
        if len(errorStatement) > 253:
            errorStatement = errorStatement[0:253]
        else:
            pass
        endTime = datetime.datetime.now()
        ScriptStatusLogging('Cansys_CMLRS_Transfer', 'SharedSDEProd.gdb\SHARED_CANSYS_CMLRS',
            scriptFailure, startTime, endTime, errorStatement, pythonLogTable)
            
        try:
            del errorItem
        except:
            pass
        
        # Reraise the error to stop execution and prevent a success message
        # from being inserted into the table.
        raise
        
    finally:
        try:
            del CMLRS_SearchCursor
        except:
            pass
        try:
            del CMLRS_InsertCursor
        except:
            pass


def manageLogLength():
    logTableDesc = Describe(pythonLogTable)
    logLengthCheckCursor = daSearchCursor(pythonLogTable, logTableDesc.OIDFieldName)

    shouldTruncate = False

    for logItem in logLengthCheckCursor:
        if int(logItem[0]) > 5000:
            shouldTruncate = True
        else:
            pass

    if shouldTruncate == True:
        print "Log table size is too big."
        print "Truncating log table."
        TruncateTable_management(pythonLogTable)
    else:
        pass


if __name__ == "__main__":
    startTime = datetime.datetime.now()
    print str(startTime) + " starting script"
    #RemoveGpHistory_fc(metadataTempFolder)
    #manageLogLength()
    transferFeatures()
    endTime = datetime.datetime.now()
    runTime = endTime - startTime
    print str(endTime) + " script completed in " + str(runTime)
    ScriptStatusLogging('Cansys_CMLRS_Transfer', 'SharedSDEProd.gdb\SHARED_CANSYS_CMLRS',
        scriptSuccess, startTime, endTime, 'Completed successfully.', pythonLogTable)
    

else:
    print "Cansys_CMLRS_Transfer script imported."