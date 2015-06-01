# Import required modules
import gzip, sys, os, threading, time, subprocess

# Set GDAL_DATA environment variable:
try:
  os.environ['GDAL_DATA'] = sys._MEIPASS
except:
  pass

from re import search

try:
  from osgeo import ogr, osr
except ImportError:
  import ogr

from PyQt4 import QtCore, QtGui
from multiprocessing.dummy import Pool as ThreadPool 

#Global counter to keep track of number of GZip files
FILECOUNTER = 0

#######################################
#######################################
# Define our translation worker class #
#######################################
#######################################

class translateWorker(threading.Thread):

  #############################
  # Define Layers for Writing #
  #############################
  def __init__(self, outputFormat, fnames, outdir):

    #British National Grid is OGC WKT format.
    self.outputCoordSystem =  """PROJCS["OSGB 1936 / British National Grid",GEOGCS["OSGB 1936",DATUM["OSGB_1936",SPHEROID["Airy 1830",6377563.396,299.3249646,AUTHORITY["EPSG","7001"]],AUTHORITY["EPSG","6277"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.01745329251994328,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4277"]],UNIT["metre",1,AUTHORITY["EPSG","9001"]],PROJECTION["Transverse_Mercator"],PARAMETER["latitude_of_origin",49],PARAMETER["central_meridian",-2],PARAMETER["scale_factor",0.9996012717],PARAMETER["false_easting",400000],PARAMETER["false_northing",-100000],AUTHORITY["EPSG","27700"],AXIS["Easting",EAST],AXIS["Northing",NORTH]]"""

    #OS VectorMap Local GML files have the following layers which will become seperate layers in ESRI Shapefile or MapInfo TAB
    self.layers = [
      "Area",
      "Line",
      "RoadCLine",
      "Text",
      "VectorMapPoint"
    ]

    #Geometry types for the layers above
    self.layerTypes = [
      ogr.wkbPolygon,
      ogr.wkbLineString,
      ogr.wkbLineString,
      ogr.wkbPoint,
      ogr.wkbPoint
    ]

    #Suffixes to create the output filename
    self.outputSuffixes = {
      "ESRI Shapefile" : "shp",
      "MapInfo File" : "TAB"
    }

    self.__outputFormat = outputFormat
    self.__outdir = outdir
    self.__fnames = fnames

    threading.Thread.__init__(self)

  ############################
  # Create Input Data Driver #
  ############################
  def inDriver(self, inFormat):
    drv = ogr.GetDriverByName (inFormat)

    # Test for driver:
    if drv is None:
      sys.exit (1)

    return drv


  #############################
  # Create Output Data Driver #
  #############################
  def outDriver(self, outFormat):
    drv = ogr.GetDriverByName (outFormat)

    # Test for driver:
    if drv is None:
      sys.exit (1)

    return drv


  #############################
  # Open Input Data Source(s) #
  #############################

  def openDataSources(self, filePath, iDriver, oDriver, oFormat, oFolder):

    splitPath = search ('(.+)\.(.\w+)', filePath)
    lastSlash = splitPath.group(1).rfind('/') + 1
    fileName = splitPath.group(1)[lastSlash::]

    ds = iDriver.Open (filePath, 0)

    # Test for data source:
    if ds is None:
      print("Failed to open file.\n")
      sys.exit (1)

    # Write layers to file:
    for i in range (len (self.layers)):
      if ds.GetLayerByName(self.layers[i]) is not None:
        self.writeLayer(i, fileName, filePath, ds, oDriver, oFormat, oFolder)


  #################################
  # Define Feature Writing Method #
  #################################

  def writeLayer (self, index, fileName, filePath, datasource, oDriver, oFormat, oFolder):
    # Create the coord ref system
    coordRefSystem = osr.SpatialReference(self.outputCoordSystem)
    # Create output file, remove if it already exists
    outName = "%s/%s_%s.%s" % (oFolder, fileName, self.layers[index], oFormat)
    if os.path.exists (outName):
      oDriver.DeleteDataSource (outName)
    outputData = oDriver.CreateDataSource (outName)

    # Create output layer
    outLyr = outputData.CreateLayer (self.layers[index], coordRefSystem, geom_type=self.layerTypes[index])

    # Get the specification of the GML layer
    lyr = datasource.GetLayerByName (self.layers[index])
    inLyrDefn = lyr.GetLayerDefn ()

    # Copy input fields to output layer
    for i in range (inLyrDefn.GetFieldCount ()):
      fieldDefn = inLyrDefn.GetFieldDefn (i)
      fieldName = fieldDefn.GetName ()
      if fieldName == 'orientation':
        fieldDefn.SetType(ogr.OFTReal)
      outLyr.CreateField (fieldDefn)

    # Get a reference to the output layer specification
    outLyrDefn = outLyr.GetLayerDefn ()

    # Write features to the output layer
    for feature in lyr:
      outFeature = ogr.Feature (outLyrDefn)

      for i in range (outLyrDefn.GetFieldCount ()):
        fieldDefn = outLyrDefn.GetFieldDefn (i)
        fieldName = fieldDefn.GetName ()
        if fieldName == 'orientatio' or fieldName == 'orientation':
          orientation = float(feature.GetField (i))/10.0
          outFeature.SetField (outLyrDefn.GetFieldDefn (i).GetNameRef (), orientation)
        else:
          outFeature.SetField (outLyrDefn.GetFieldDefn (i).GetNameRef (), feature.GetField (i))

      geom = feature.GetGeometryRef()
      outFeature.SetGeometry(geom.Clone())

      outLyr.CreateFeature(outFeature)

    outputData.Destroy()


  ##############################
  # Define thread entry method #
  ##############################

  def run(self):

    # Load input driver
    start_time = time.time()
    self.inputDriver = self.inDriver("GML")

    # Load output driver
    self.outputDriver = self.outDriver(self.__outputFormat)

    # Open data sources to convert and write to file.
    self.openDataSources(self.__fnames, self.inputDriver, self.outputDriver, self.outputSuffixes[self.__outputFormat], self.__outdir)

    # Clean up processing files (.gfs).
    if type(self.__fnames) == list:
      for filepath in self.__fnames:
        extension = filepath.rfind('.')
        gfsPath = filepath[0:extension] + '.gfs'
        os.remove(gfsPath)
    else:
      extension = self.__fnames.rfind('.')
      gfsPath = self.__fnames[0:extension] + '.gfs'
      os.remove(gfsPath)

    end_time = time.time()
    time_taken = end_time-start_time

    log_message = "File %s translated in %.2fs." % (self.__fnames, time_taken)
    print log_message

    return


#################################
#################################
# Define our file browser class #
#################################
#################################

class BrowseThread(QtCore.QThread):

    # Set up GUI signal handlers.
    browse_finished = QtCore.pyqtSignal(object)

    def __init__(self, data_dir):
        QtCore.QThread.__init__(self)
        self.data_dir = str(data_dir) 

    def run(self):
        fileList = []
        global FILECOUNTER

        # Walk through the source directory looking for GZip Files (*.gz)
        for dirname, dirnames, filenames in os.walk(self.data_dir):
            for filename in filenames:
                if filename.endswith(".gz"):
                    full_path = r'%s/%s'%(self.data_dir,filename)
                    fileList.append(full_path) # Append the full path so this can be used during translating
                    FILECOUNTER += 1 # Update the filecounter
        
        # Emit the fileList as an object back to the main thread
        self.browse_finished.emit(fileList)


######################################
######################################
# Define our translate manager class #
######################################
######################################

class TranslateThread(QtCore.QThread):

    # Set up GUI signal handlers.
    translate_finished = QtCore.pyqtSignal(object)
    translate_during = QtCore.pyqtSignal(object)
    translate_thread_complete = QtCore.pyqtSignal(object)

    def __init__(self, fileList, output_format, output_directory):
        QtCore.QThread.__init__(self)

        # Process the supplied list of files, output format and output directory into class variables.
        self.fileList = fileList
        self.output_directory = str(output_directory)
        self.output_format = output_format

    def threadControl(self, __filePath):
        # Get the file name from the path to use in GUI messages.
        fileName = os.path.splitext(os.path.basename(__filePath))[0]

        # Log the start of the translate task to the GUI.
        self.translate_during.emit(fileName) 

        # Create a translate worker thread with the proveded file path, output format and output directory.
        thread = translateWorker(self.output_format, __filePath, self.output_directory)

        # Start the worker.
        thread.start()

        # Wait for the worker to exit.
        thread.join()

        # Log the completion of the translate task to the GUI.
        self.translate_thread_complete.emit(fileName)
        return

    def run(self):
        # Create a pool to manage translate workers.
        pool = ThreadPool(processes=36)

        # For each filepath in the filelist, run the *threadControl* method to create a translate worker and run it.
        pool.map(self.threadControl, self.fileList)

        # Close the pool.
        pool.close()

        # Wait for the worker processes to exit.
        pool.join()

        # Log a 'translation finished' message to the GUI.
        self.translate_finished.emit("done")


########################
########################
# Define our GUI class #
########################
########################       

class MainWindow(QtGui.QWidget):
    def __init__(self):
        super(MainWindow, self).__init__()

        def resource_path(relative_path):
            """ Get absolute path to resource, works for dev and for PyInstaller """
            try:
                # PyInstaller creates a temp folder and stores path in _MEIPASS
                base_path = sys._MEIPASS
            except Exception:
                base_path = os.path.abspath(".")

            return os.path.join(base_path, relative_path)

        self.source_directory = ""
        self.output_directory = ""
        self.outputFormat = ""

        self.osicon = resource_path("os_logo.png")

        # Setup the GUI with the following widgets and items
        self.setWindowTitle('Icon')
        self.setWindowIcon(QtGui.QIcon(self.osicon))

        self.browseBtn = QtGui.QPushButton("Select Source Folder")
        self.browseBtn.clicked.connect(self.sourceFolderDialog)

        self.outputBtn = QtGui.QPushButton("Select Output Folder")
        self.outputBtn.clicked.connect(self.outputFolderDialog)

        self.formatBox = QtGui.QComboBox(self)
        self.formatBox.addItem("Pick an Output Format")
        self.formatBox.addItem("ESRI Shapefile")
        self.formatBox.addItem("MapInfo File")
        self.formatBox.activated[str].connect(self.onFormat)
        
        self.translateBtn = QtGui.QPushButton("Translate Files")
        self.translateBtn.clicked.connect(self.translateFiles)   

        self.log = QtGui.QTextEdit()
        self.log.setReadOnly(True)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())
        self.log.setFontPointSize(9.0)     

        self.quitBtn = QtGui.QPushButton('Quit', self)
        self.quitBtn.clicked.connect(self.quit)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.browseBtn)
        layout.addWidget(self.outputBtn)
        layout.addWidget(self.formatBox)
        layout.addWidget(self.translateBtn)
        layout.addWidget(self.log)
        layout.addWidget(self.quitBtn)
        self.setLayout(layout)

        self.center() # Starts the center function which centers the application 

    def sourceFolderDialog(self):
        self.source_directory = QtGui.QFileDialog.getExistingDirectory(None, 'Select a folder:', 'C:\\', QtGui.QFileDialog.ShowDirsOnly)
        self.log.append("Source Directory: " + self.source_directory)
        self.browseFiles()

    def outputFolderDialog(self):
        self.output_directory = QtGui.QFileDialog.getExistingDirectory(None, 'Select a folder:', 'C:\\', QtGui.QFileDialog.ShowDirsOnly)
        self.log.append("Output Directory: " + self.output_directory)

    def browseFiles(self):
        self.threads = []
        browse = BrowseThread(self.source_directory)
        browse.browse_finished.connect(self.splitFiles)
        self.threads.append(browse)
        browse.start()

    def splitFiles(self, data):
        self.log.append("Number of Files: " + str(FILECOUNTER))
        if FILECOUNTER == 0:
          QtGui.QMessageBox.warning(self,"Warning", "No gz files found, please select a different directory")
          self.source_directory = ""
        else:
          self.fileList = data

    def onFormat(self, text): # Checks that an Output Format has been selected
      if str(text) == "Pick an Output Format":
        self.log.append("Please Select an Output Format")
        QtGui.QMessageBox.warning(self,"Warning", "Please Select an Output Format")
      else:
        self.outputFormat = str(text)

        drv = ogr.GetDriverByName (self.outputFormat)

        self.log.append("Output Format: " + self.outputFormat)

    def translateFiles(self): # Starts the TranslateThread
        self.start_time = time.time()

        if self.source_directory == "":
          print "no source directory chosen"
          QtGui.QMessageBox.warning(self,"Warning", "No source directory chosen")

        elif self.output_directory == "":
          print "no output directory chosen"
          QtGui.QMessageBox.warning(self,"Warning", "No output directory chosen")

        elif self.outputFormat == "":
          print "no output format chosen"
          QtGui.QMessageBox.warning(self,"Warning", "No output format chosen")

        else:
          self.browseBtn.setEnabled(False)
          self.outputBtn.setEnabled(False)
          self.formatBox.setEnabled(False)
          self.translateBtn.setEnabled(False)
          translate = TranslateThread(self.fileList, self.outputFormat, self.output_directory)
          translate.translate_during.connect(self.duringTranslate)
          translate.translate_thread_complete.connect(self.threadComplete)
          translate.translate_finished.connect(self.afterTranslate)
          self.threads.append(translate)
          translate.start()

    def duringTranslate(self, data): # Updates the log stating which file is being translated
        self.log.append("Translating File " + data)

    def threadComplete(self, data): # Updates the log confirming file has been translated and the time taken
        self.log.append("File " + data + " translated successfully.")


    def afterTranslate(self):
        time_taken = time.time() - self.start_time
        self.log.setFontPointSize(13.0)
        self.log.append("Successfully Translated Files in %.2f seconds." % time_taken) # Append to log window to notify translation has finished 
        self.quitBtn.setEnabled(True) # Enable the button giving user an option to exit the application
        self.browseBtn.setEnabled(True)
        self.outputBtn.setEnabled(True)
        self.formatBox.setEnabled(True)
        self.translateBtn.setEnabled(True)
        self.log.setFontPointSize(9.0)
        self.source_directory = ""
        self.output_directory = ""
        self.outputFormat = ""


    def center(self): # Function to center the application on the desktop      
        qr = self.frameGeometry()
        cp = QtGui.QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def closeEvent(self, event):   # Event to manage when the user clicks the 'X' icon on the application      
        reply = QtGui.QMessageBox.question(self, 'Quit?', "Are you sure you want to exit the program?", QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)

        if reply == QtGui.QMessageBox.Yes:
            event.accept()
        else:
            event.ignore() 

    def quit(self):
      reply = QtGui.QMessageBox.question(self, 'Quit?', "Are you sure you want to exit the program?", QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)

      if reply == QtGui.QMessageBox.Yes:
          QtCore.QCoreApplication.instance().quit()
      else:
          event.ignore() 


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = MainWindow()
    window.resize(640, 480)
    window.setWindowTitle('OS VectorMap Local Translator')
    window.show()
    sys.exit(app.exec_())