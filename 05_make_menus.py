# !/bin/env/python
# An introduction sample source code that provides RP1210 capabilities

# Import
from PyQt5.QtWidgets import (QMainWindow,
                             QWidget,
                             QTreeView,
                             QMessageBox,
                             QFileDialog,
                             QLabel,
                             QSlider,
                             QCheckBox,
                             QLineEdit,
                             QVBoxLayout,
                             QApplication,
                             QPushButton,
                             QTableWidget,
                             QTableView,
                             QTableWidgetItem,
                             QScrollArea,
                             QAbstractScrollArea,
                             QAbstractItemView,
                             QSizePolicy,
                             QGridLayout,
                             QGroupBox,
                             QComboBox,
                             QAction,
                             QDockWidget,
                             QDialog,
                             QDialogButtonBox,
                             QInputDialog,
                             QProgressDialog)
from PyQt5.QtCore import Qt, QTimer, QCoreApplication
from PyQt5.QtGui import QIcon

# Use ctypes to import the RP1210 DLL
from ctypes import *
from ctypes.wintypes import HWND

# Use threads to set up asynchronous communications
import threading
import queue
import time
import collections
import sys
import struct
import json

import configparser

from RP1210Constants import *


class RP1210ReadMessageThread(threading.Thread):
    '''This thread is designed to recieve messages from the vehicle diagnostic
    adapter (VDA) and put thedata into a queue. The class arguments are as
    follows:
    rx_queue - A datastructure that takes the recieved message.
    RP1210_ReadMessage - a function handle to the VDA DLL.
    nClientID - this lets us know which network is being used to recieve the
                messages. This will likely be a 1 or 2'''

    def __init__(self, parent, rx_queue, RP1210_ReadMessage, nClientID):
        threading.Thread.__init__(self)
        self.root = parent
        self.rx_queue = rx_queue
        self.RP1210_ReadMessage = RP1210_ReadMessage
        self.nClientID = nClientID
        self.runSignal = True

    def run(self):
        ucTxRxBuffer = (c_char * 2000)()
        # display a valid connection upon start.
        print("Read Message Client ID: {}".format(self.nClientID))
        while self.runSignal:
            return_value = self.RP1210_ReadMessage(c_short(self.nClientID),
                                                   byref(ucTxRxBuffer),
                                                   c_short(2000),
                                                   c_short(BLOCKING_IO))
            if return_value > 0:
                self.rx_queue.put(ucTxRxBuffer[:return_value])
            time.sleep(.0005)
        print("RP1210 Receive Thread is finished.")


class RP1210Class():
    """A class to access RP1210 libraries for different devices."""
    def __init__(self,dll_name,protocol,deviceID,speed):        
        #Load the Windows Device Library
        self.nClientID = None
        if dll_name is not None and protocol is not None and deviceID is not None:
            print("Loading the {} file using the {} protocol for device {:d}".format(dll_name + ".dll", protocol, deviceID))
            try:
                RP1210DLL = windll.LoadLibrary(dll_name + ".dll")
            except Exception as e:
                print(e)
                print("\nIf RP1210 DLL fails to load, please check to be sure you are using"
                    + "a 32-bit version of Python and you have the correct drivers for the VDA installed.")
                return None

            # Define windows prototype functions:
            try:
                prototype = WINFUNCTYPE(c_short, HWND, c_short, c_char_p, c_long, c_long, c_short)
                self.ClientConnect = prototype(("RP1210_ClientConnect", RP1210DLL))

                prototype = WINFUNCTYPE(c_short, c_short)
                self.ClientDisconnect = prototype(("RP1210_ClientDisconnect", RP1210DLL))

                prototype = WINFUNCTYPE(c_short, c_short,  POINTER(c_char*2000), c_short, c_short, c_short)
                self.SendMessage = prototype(("RP1210_SendMessage", RP1210DLL))

                prototype = WINFUNCTYPE(c_short, c_short, POINTER(c_char*2000), c_short, c_short)
                self.ReadMessage = prototype(("RP1210_ReadMessage", RP1210DLL))

                prototype = WINFUNCTYPE(c_short, c_short, c_short, POINTER(c_char*2000), c_short)
                self.SendCommand = prototype(("RP1210_SendCommand", RP1210DLL))
            except Exception as e:
                print(e)
                print("\n Critical RP1210 functions were not able to be loaded. There is something wrong with the DLL file.")
                return None
            
            try:
                prototype = WINFUNCTYPE(c_short, c_char_p, c_char_p, c_char_p, c_char_p)
                self.ReadVersion = prototype(("RP1210_ReadVersion", RP1210DLL))
            except Exception as e:
                print(e)
            
            try:
                prototype = WINFUNCTYPE(c_short, c_short, POINTER(c_char*17), POINTER(c_char*17), POINTER(c_char*17))
                self.ReadDetailedVersion  = prototype(("RP1210_ReadDetailedVersion", RP1210DLL))
            except Exception as e:
                print(e)
                self.ReadDetailedVersion = None

            try:
                prototype = WINFUNCTYPE(c_short, c_short, POINTER(c_char*64), c_short, c_short)
                self.GetHardwareStatus = prototype(("RP1210_GetHardwareStatus", RP1210DLL))
            except Exception as e:
                print(e)
                self.GetHardwareStatus = None
            try:
                prototype = WINFUNCTYPE(c_short, c_short, POINTER(c_char*256))
                self.GetHardwareStatusEx = prototype(("RP1210_GetHardwareStatusEx", RP1210DLL))
            except Exception as e:
                print(e)
                self.GetHardwareStatusEx = None

            try:
                prototype = WINFUNCTYPE(c_short, c_short, POINTER(c_char*80))
                self.GetErrorMsg = prototype(("RP1210_GetErrorMsg", RP1210DLL))
            except Exception as e:
                print(e)
                self.GetErrorMsg = None
            
            try:
                prototype = WINFUNCTYPE(c_short, c_short, POINTER(c_int), POINTER(c_char*80), c_short)
                self.GetLastErrorMsg = prototype(("RP1210_GetLastErrorMsg", RP1210DLL))
            except Exception as e:
                print(e)
                self.GetLastErrorMsg = None
            


            if len(speed) > 0 and (protocol == "J1939"  or protocol == "CAN" or protocol == "ISO15765"):
                protocol_bytes = bytes(protocol + ":Baud={}".format(speed),'ascii')
            else:
                protocol_bytes = bytes(protocol,'ascii')
            print("Connecting to ClientConnect using ", end = '')
            print(protocol_bytes)
            # if self.nClientID in locals():
            #     return_value = self.RP1210.ClientDisconnect(self.nClientID)
            #     print("Exiting. RP1210_ClientDisconnect returns {}: {}".format(return_value,RP1210Errors[return_value]))
            try:
                self.nClientID = self.ClientConnect(HWND(None), c_short(deviceID), protocol_bytes, 0, 0, 0)
                print("The Client ID is: {}".format(self.nClientID))
            except Exception as e:
                print(e)
            

class SelectRP1210(QDialog):
    def __init__(self):
        super(SelectRP1210,self).__init__()
        RP1210_config = configparser.ConfigParser()
        RP1210_config.read("c:/Windows/RP121032.ini")
        self.apis = sorted(RP1210_config["RP1210Support"]["apiimplementations"].split(","))
        self.current_api_index = 0
        print("Current RP1210 APIs installed are: " + ", ".join(self.apis))
        self.dll_name = None
        self.setup_dialog()
        self.setWindowTitle("Select RP1210")
        self.setWindowModality(Qt.ApplicationModal)
        self.exec_()

    def setup_dialog(self):
        
        vendor_label = QLabel("System RP1210 Vendors:")
        self.vendor_combo_box = QComboBox()
        self.vendor_combo_box.setInsertPolicy(QComboBox.NoInsert)
        self.vendor_combo_box.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.vendor_combo_box.activated.connect(self.fill_device)

        device_label = QLabel("Available RP1210 Vendor Devices:")
        self.device_combo_box = QComboBox()
        self.device_combo_box.setInsertPolicy(QComboBox.NoInsert)
        self.device_combo_box.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.device_combo_box.activated.connect(self.fill_protocol)
        
        protocol_label = QLabel("Available Device Protocols:")
        self.protocol_combo_box = QComboBox()
        self.protocol_combo_box.setInsertPolicy(QComboBox.NoInsert)
        self.protocol_combo_box.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.protocol_combo_box.activated.connect(self.fill_speed)
        
        speed_label = QLabel("Available Speed Settings")
        self.speed_combo_box = QComboBox()
        self.speed_combo_box.setInsertPolicy(QComboBox.NoInsert)
        self.speed_combo_box.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        self.accepted.connect(self.connect_RP1210)
        self.rejected.connect(self.reject_RP1210)
        
        try:
            with open("RP1210_selection.txt","r") as selection_file:
                previous_selections = selection_file.read()
        except FileNotFoundError:
            print("RP1210_selection.txt not Found!")
            previous_selections = "0,0,0"
        self.selection_index = previous_selections.split(',')

        self.fill_vendor()

        self.v_layout = QVBoxLayout()
        self.v_layout.addWidget(vendor_label)
        self.v_layout.addWidget(self.vendor_combo_box)
        self.v_layout.addWidget(device_label)
        self.v_layout.addWidget(self.device_combo_box)
        self.v_layout.addWidget(protocol_label)
        self.v_layout.addWidget(self.protocol_combo_box)
        self.v_layout.addWidget(speed_label)
        self.v_layout.addWidget(self.speed_combo_box)
        self.v_layout.addWidget(self.buttons)

        self.setLayout(self.v_layout)

    def fill_vendor(self):
        self.vendor_combo_box.clear()
        self.vendor_configs = {} 
        for api_string in self.apis:
            self.vendor_configs[api_string] = configparser.ConfigParser()
            try:
                self.vendor_configs[api_string].read("c:/Windows/" + api_string + ".ini")
                #print("api_string = {}".format(api_string))
                #print("The api ini file has the following sections:")
                #print(vendor_config.sections())
                vendor_name = self.vendor_configs[api_string]['VendorInformation']['name']
                #print(vendor_name)
                if vendor_name is not None:
                    vendor_combo_box_entry = "{:8} - {}".format(api_string,vendor_name)
                    if len(vendor_combo_box_entry) > 0:
                        self.vendor_combo_box.addItem(vendor_combo_box_entry)
                else:
                    self.apis.remove(api_string) #remove faulty/corrupt api_string   
            except Exception as e:
                print(e)
                self.apis.remove(api_string) #remove faulty/corrupt api_string 
        try:
            self.vendor_combo_box.setCurrentIndex(int(self.selection_index[0]))
        except:
            pass

        if self.vendor_combo_box.count() > 0:
            self.fill_device()
        else:
            print("There are no entries in the RP1210 Vendor's ComboBox.")

    def fill_device(self):
        self.api_string = self.vendor_combo_box.currentText().split("-")[0].strip()
        self.device_combo_box.clear()
        self.protocol_combo_box.clear()
        self.speed_combo_box.clear()
        for key in self.vendor_configs[self.api_string]:
            if "DeviceInformation" in key:
                try:
                    device_id = self.vendor_configs[self.api_string][key]["DeviceID"]
                except KeyError:
                    device_id = None
                    print("No Device ID for {} in {}.ini".format(key,self.api_string))
                try:
                    device_description = self.vendor_configs[self.api_string][key]["DeviceDescription"]
                except KeyError:
                    device_description = "No device description available"
                try:
                    device_MultiCANChannels = self.vendor_configs[self.api_string][key]["MultiCANChannels"]
                except KeyError:
                    device_MultiCANChannels = None
                try:
                    device_MultiJ1939Channels = self.vendor_configs[self.api_string][key]["MultiJ1939Channels"]
                except KeyError:
                    device_MultiJ1939Channels = None
                try:
                    device_MultiISO15765Channels = self.vendor_configs[self.api_string][key]["MultiISO15765Channels"]
                except KeyError:
                    device_MultiISO15765Channels = None
                try:
                    device_name = self.vendor_configs[self.api_string][key]["DeviceName"]
                except KeyError:
                    device_name = "Device name not provided"
                device_combo_box_entry = "{}: {}, {}".format(device_id,device_name,device_description)
                if len(device_combo_box_entry) > 0:
                    self.device_combo_box.addItem(device_combo_box_entry)
        try:
            self.device_combo_box.setCurrentIndex(int(self.selection_index[1]))
        except:
            pass   
        self.fill_protocol()

    def fill_protocol(self):

        self.protocol_combo_box.clear()
        self.speed_combo_box.clear()
        if self.device_combo_box.currentText() == "":
                self.device_combo_box.setCurrentIndex(0)
        self.device_id = self.device_combo_box.currentText().split(":")[0].strip()

        self.protocol_speed = {}
        for key in self.vendor_configs[self.api_string]:
            if "ProtocolInformation" in key:
                try:
                    protocol_string = self.vendor_configs[self.api_string][key]["ProtocolString"]
                except KeyError:
                    protocol_string = None
                    print("No Protocol Name for {} in {}.ini".format(key,self.api_string))
                try:
                    protocol_description = self.vendor_configs[self.api_string][key]["ProtocolDescription"]
                except KeyError:
                    protocol_description = "No protocol description available"
                try:
                    if protocol_string is not None:
                        self.protocol_speed[protocol_string] = self.vendor_configs[self.api_string][key]["ProtocolSpeed"]
                    else:
                        self.protocol_speed[protocol_string] = ""
                except KeyError:
                    self.protocol_speed[protocol_string] = ""
                try:
                    protocol_params = self.vendor_configs[self.api_string][key]["ProtocolParams"]
                except KeyError:
                    protocol_params = ""
                
                devices = self.vendor_configs[self.api_string][key]["Devices"].split(',')
                if self.device_id in devices and protocol_string is not None:
                    device_combo_box_entry = "{}: {}".format(protocol_string,protocol_description)
                    self.protocol_combo_box.addItem(device_combo_box_entry)
            else:
                pass    
        try:
            self.protocol_combo_box.setCurrentIndex(int(self.selection_index[2]))
            
        except Exception as e:
            print(e) 
        self.fill_speed()

    def fill_speed(self):
        self.speed_combo_box.clear()
        if self.protocol_combo_box.currentText() == "":
                self.protocol_combo_box.setCurrentIndex(0)
        self.device_id = self.device_combo_box.currentText().split(":")[0].strip()
        protocol_string = self.protocol_combo_box.currentText().split(":")[0].strip()
        print(protocol_string)
        print(self.protocol_speed[protocol_string])
        try:
            protocol_speed = sorted(self.protocol_speed[protocol_string].strip().split(','),reverse=True)
            self.speed_combo_box.addItems(protocol_speed)
        except Exception as e:
            print(e) 

    def connect_RP1210(self):
        print("Accepted Dialog OK")
        vendor_index = self.vendor_combo_box.currentIndex()
        device_index = self.device_combo_box.currentIndex()
        protocol_index = self.protocol_combo_box.currentIndex()
        speed_index = self.speed_combo_box.currentIndex()

        with open("RP1210_selection.txt","w") as selection_file:
            selection_file.write("{},{},{}".format(vendor_index,device_index,protocol_index,speed_index))
        self.dll_name = self.vendor_combo_box.itemText(vendor_index).split("-")[0].strip()
        self.deviceID = int(self.device_combo_box.itemText(device_index).split(":")[0].strip())
        self.speed = self.speed_combo_box.itemText(speed_index)
        self.protocol = self.protocol_combo_box.itemText(protocol_index).split(":")[0].strip()
        file_contents={"dll_name":self.dll_name,"protocol":self.deviceID,"deviceID":self.protocol,"speed":self.speed}
        with open("Last_RP1210_Connection.json","w") as rp1210_file:
                 json.dump(file_contents,rp1210_file)
    
    def reject_RP1210(self):
        self.dll_name = None
        self.protocol = None
        self.deviceID = None
        self.speed = None


class TUDiagnostics(QMainWindow):
    def __init__(self):
        super(TUDiagnostics,self).__init__()
        self.setGeometry(200,200,700,500)
        self.init_ui()
        self.selectRP1210(automatic=True)

    def init_ui(self):
        # Builds GUI
        # Start with a status bar
        self.statusBar().showMessage("Welcome!")
        
        # Build common menu options
        menubar = self.menuBar()
        
        # File Menu Items
        file_menu = menubar.addMenu('&File')
        open_file = QAction(QIcon(r'icons/icons8_Open_48px_1.png'), '&Open', self)
        open_file.setShortcut('Ctrl+O')
        open_file.setStatusTip('Open new File')
        open_file.triggered.connect(self.open_file)
        file_menu.addAction(open_file)

        # RP1210 Menu Items
        rp1210_menu = menubar.addMenu('&RP1210')
        connect_rp1210 = QAction(QIcon(r'icons/icons8_Connected_48px.png'), '&Client Connect', self)
        connect_rp1210.setShortcut('Ctrl+Shift+C')
        connect_rp1210.setStatusTip('Connect Vehicle Diagnostic Adapter')
        connect_rp1210.triggered.connect(self.selectRP1210)
        rp1210_menu.addAction(connect_rp1210)

        rp1210_version = QAction(QIcon(r'icons/icons8_Versions_48px.png'), '&Driver Version', self)
        rp1210_version.setShortcut('Ctrl+Shift+V')
        rp1210_version.setStatusTip('Show Vehicle Diagnostic Adapter Driver Version Information') 
        rp1210_version.triggered.connect(self.display_version)
        rp1210_menu.addAction(rp1210_version)
        
        rp1210_detailed_version = QAction(QIcon(r'icons/icons8_More_Details_48px.png'), 'De&tailed Version', self)
        rp1210_detailed_version.setShortcut('Ctrl+Shift+T')
        rp1210_detailed_version.setStatusTip('Show Vehicle Diagnostic Adapter Detailed Version Information') 
        rp1210_detailed_version.triggered.connect(self.display_detailed_version)
        rp1210_menu.addAction(rp1210_detailed_version)
        
        rp1210_get_error_msg = QAction(QIcon(r'icons/icons8_Attention_48px_1.png'), '&Lookup Error Message', self)
        rp1210_get_error_msg.setShortcut('Ctrl+Shift+L')
        rp1210_get_error_msg.setStatusTip('Translates an RP1210 error code into a textual description of the error.') 
        rp1210_get_error_msg.triggered.connect(self.lookup_error_code)
        rp1210_menu.addAction(rp1210_get_error_msg)

        rp1210_get_last_error_msg = QAction(QIcon(r'icons/icons8_Error_48px.png'), 'Lookup Last Error &Message', self)
        rp1210_get_last_error_msg.setShortcut('Ctrl+Shift+M')
        rp1210_get_last_error_msg.setStatusTip('Translates an RP1210 error code into a more detailed error code and textual description.') 
        rp1210_get_last_error_msg.triggered.connect(self.get_last_error_msg)
        rp1210_menu.addAction(rp1210_get_last_error_msg)

        rp1210_get_hardware_status = QAction(QIcon(r'icons/icons8_Steam_48px.png'), 'Get &Hardware Status', self)
        rp1210_get_hardware_status.setShortcut('Ctrl+Shift+H')
        rp1210_get_hardware_status.setStatusTip('Determine details regarding the hardware interface status and its connections.') 
        rp1210_get_hardware_status.triggered.connect(self.get_hardware_status)
        rp1210_menu.addAction(rp1210_get_hardware_status)

        rp1210_get_hardware_status_ex = QAction(QIcon(r'icons/icons8_System_Information_48px.png'), 'Get &Extended Hardware Status', self)
        rp1210_get_hardware_status_ex.setShortcut('Ctrl+Shift+E')
        rp1210_get_hardware_status_ex.setStatusTip('Determine the hardware interface status and whether the VDA device is physically connected.') 
        rp1210_get_hardware_status_ex.triggered.connect(self.get_hardware_status_ex)
        rp1210_menu.addAction(rp1210_get_hardware_status_ex)

        disconnect_rp1210 = QAction(QIcon(r'icons/icons8_Disconnected_48px.png'), 'Client &Disconnect', self)
        disconnect_rp1210.setShortcut('Ctrl+Shift+D')
        disconnect_rp1210.setStatusTip('Disconnect all RP1210 Clients')
        disconnect_rp1210.triggered.connect(self.disconnectRP1210)
        rp1210_menu.addAction(disconnect_rp1210)

        help_menu = menubar.addMenu('&Help')
        about = QAction(QIcon(r'icons/icons8_Help_48px_1.png'), 'A&bout', self)
        about.setShortcut('Ctrl+B')
        about.setStatusTip('Display a dialog box with information about the program.')
        about.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about)
       
        #build the entries in the dockable tool bar
        RP1210_toolbar = self.addToolBar("Main")
        RP1210_toolbar.addAction(connect_rp1210)
        RP1210_toolbar.addAction(rp1210_version)
        RP1210_toolbar.addAction(rp1210_detailed_version)
        RP1210_toolbar.addAction(rp1210_get_error_msg)
        RP1210_toolbar.addAction(rp1210_get_last_error_msg)
        RP1210_toolbar.addAction(rp1210_get_hardware_status)
        RP1210_toolbar.addAction(rp1210_get_hardware_status_ex)
        RP1210_toolbar.addAction(disconnect_rp1210)

        get_vin_button = QPushButton('Request VIN on J1939')        
        get_vin_button.clicked.connect(self.get_j1939_vin)        
        self.scroll_CAN_message_button =  QCheckBox("Auto Scroll Message Window")   


        #Set up a Table to display recieved messages
        self.received_CAN_message_table = QTableWidget()
        
        #Set the headers
        CAN_table_columns = ["Count","PC Time","VDA Time","ID","DLC","B0","B1","B2","B3","B4","B5","B6","B7"]
        self.received_CAN_message_table.setColumnCount(len(CAN_table_columns))
        self.received_CAN_message_table.setHorizontalHeaderLabels(CAN_table_columns)
        
        #Initialize a counter
        self.received_CAN_message_count = 0
        #use this variable to run a reziser once message traffic appears
        self.received_CAN_message_table_needs_resized = True
        
        self.max_rx_messages = 10000
        self.rx_message_buffer = collections.deque(maxlen=self.max_rx_messages)
        self.max_message_table = 10000
        self.message_table_ids=collections.deque(maxlen=self.max_message_table)
        
        
        #self.fill_table()

        grid_layout = QGridLayout()
        #Define where the widgets go in the window        
        #Grid layouts have the addWidget arguement with the following form:
        # grid_layout.addWidget(widget,row,column,rowspan,colspan)
        grid_layout.addWidget(get_vin_button,0,0,1,1)
        grid_layout.addWidget(self.scroll_CAN_message_button,1,0,1,1)
        grid_layout.addWidget(self.received_CAN_message_table,2,0,1,1)
        

        main_widget = QWidget()
        main_widget.setLayout(grid_layout)
        self.setCentralWidget(main_widget)
        self.setWindowTitle('RP1210 Interface')
        self.show()

    def selectRP1210(self,automatic=False):

        try:
            nClientID = self.RP1210.nClientID
            if nClientID is not None:
                return_value = self.RP1210.ClientDisconnect(nClientID)
                print("Exiting. RP1210_ClientDisconnect returns {}: {}".format(return_value,RP1210Errors[return_value]))
        except AttributeError:
            pass

        if automatic:
            try:
                # The json file holding the last connection of the RP1210 device is
                # a dictionary of dictionarys where the main keys are the client ids
                # and the entries are a dictionary needed for the connections. 
                # This enables us to connect 2 or more clients at once and remember.
                with open("Last_RP1210_Connection.json","r") as rp1210_file:
                    file_contents = json.load(rp1210_file)
                for clientID,select_dialog in file_contents.items():
                    dll_name = select_dialog["dll_name"]
                    protocol = select_dialog["protocol"]
                    deviceID = select_dialog["deviceID"]
                    speed = select_dialog["speed"]
                    self.RP1210 = RP1210Class(dll_name,protocol,deviceID,speed)
                    
            except Exception as e:
                print(e)
                selection = SelectRP1210()
                dll_name = selection.dll_name
                protocol = selection.protocol
                deviceID = selection.deviceID
                speed = selection.speed
                self.RP1210 = RP1210Class(dll_name,protocol,deviceID,speed)

        else:
            selection = SelectRP1210()
            dll_name = selection.dll_name
            protocol = selection.protocol
            deviceID = selection.deviceID
            speed = selection.speed
            self.RP1210 = RP1210Class(dll_name, protocol, deviceID, speed)
   
        nClientID = self.RP1210.nClientID
        if nClientID is None:
            print("An RP1210 device is not connected properly.")
            return

        while nClientID > 127:
            question_text = "The return value is {}: {}.\n".format(nClientID,
                            self.get_error_code(nClientID))
            question_text += "Do you want to try again?"
            reply = QMessageBox.question(self, "Connection Issue",
                                                question_text,
                                                QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                selection = SelectRP1210()
                dll_name = selection.dll_name
                protocol = selection.protocol
                deviceID = selection.deviceID
                speed = selection.speed
                self.RP1210 = RP1210Class(dll_name, protocol, deviceID, speed)
                nClientID = self.RP1210.nClientID
            else:
                return

        if nClientID < 128 and nClientID is not None: 
            file_contents = {nClientID:{"dll_name":dll_name,
                                             "protocol":protocol,
                                             "deviceID":deviceID,
                                             "speed":speed}
                                            }
            with open("Last_RP1210_Connection.json","w") as rp1210_file:
                json.dump(file_contents, rp1210_file, sort_keys=True, indent = 4)
        
            # Set all filters to pass.  This allows messages to be read.
            # Constants are defined in an included file
            return_value = self.RP1210.SendCommand(c_short(RP1210_Set_All_Filters_States_to_Pass), c_short(nClientID), None, 0)
            if return_value == 0:
                print("RP1210_Set_All_Filters_States_to_Pass - SUCCESS")
            else :
                print('RP1210_Set_All_Filters_States_to_Pass returns {:d}: {}'.format(return_value,RP1210Errors[return_value]))
                return

            #setup a Receive queue. This keeps the GUI responsive and enables messages to be received.
            self.rx_queue = queue.Queue()
            self.read_message_thread = RP1210ReadMessageThread(self, self.rx_queue,self.RP1210.ReadMessage,nClientID)
            self.read_message_thread.setDaemon(True) #needed to close the thread when the application closes.
            self.read_message_thread.start()
            print("Started RP1210ReadMessage Thread.")
            
            self.statusBar().showMessage("{} connected using {}".format(protocol,dll_name))
            
            #set up an event timer to fill a table of received messages
            table_timer = QTimer(self)
            table_timer.timeout.connect(self.fill_table)
            table_timer.start(20)
        else:
            print("There was an error. Client ID is {}".format(nClientID))

    def get_j1939_vin(self):
        """An Example of requesting a VIN over J1939"""
        nClientID = self.RP1210.nClientID
        if nClientID is not None or nClientID < 128:
            pgn = 65260
            print("PGN: {:X}".format(pgn))
            b0 = pgn & 0xff
            print("b0 = {:02X}".format(b0))
            b1 = (pgn & 0xff00) >> 8
            print("b1 = {:02X}".format(b1))
            dlc = 3
            b2 = 0 #(pgn & 0xff0000) >> 16

            #initialize the buffer
            ucTxRxBuffer = (c_char*2000)()
            
            ucTxRxBuffer[0]=0x01 #Message type is extended per RP1210
            ucTxRxBuffer[1]=0x18 #Priority 6
            ucTxRxBuffer[2]=0xEA #Request PGN
            ucTxRxBuffer[3]=0x00 #Destination address of Engine
            ucTxRxBuffer[4]=0xF9 #Source address of VDA
            ucTxRxBuffer[5]=b0
            ucTxRxBuffer[6]=b1
            ucTxRxBuffer[7]=b2
            
            msg_len = 8
                
            return_value = self.RP1210.SendMessage(c_short(nClientID),
                                            byref(ucTxRxBuffer),
                                            c_short(msg_len), 0, 0)
            if return_value != 0:
                message_window = QMessageBox()
                message_window.setIcon(QMessageBox.Information)
                message_window.setWindowTitle('RP1210 Return Value')
                message_window.setStandardButtons(QMessageBox.Ok)
                if return_value in RP1210Errors:
                    print("RP1210_SendMessage fails with a return value of  {}: {}".format(return_value,RP1210Errors[return_value]))
                    message_window.setText("RP1210_SendMessage failed with\na return value of  {}: {}".format(return_value,RP1210Errors[return_value]))
                else:
                    message_window.setText("RP1210_SendMessage failed with\nan unknown error. Code: {}".format(return_value))
                    print("return value: {}: {}".format(return_value,RP1210Errors[return_value]))
                message_window.exec_()

        else:
            print("RP1210 Device Needs to be Connected")
            message_window = QMessageBox()
            message_window.setText("RP1210 Device Needs to be Connected For This Feature to Work.")
            message_window.setIcon(QMessageBox.Information)
            message_window.setWindowTitle('RP1210 Connection Issue')
            message_window.setStandardButtons(QMessageBox.Ok)
            message_window.exec_()

    def open_file(self):
        print("Open Data")  

    
    def fill_table(self):
        #check to see if something is in the queue
        while self.rx_queue.qsize():
            
            #Get a message from the queue. These are raw bytes
            rxmessage = self.rx_queue.get()
            
            if self.scroll_CAN_message_button.isChecked():
                self.received_CAN_message_table.scrollToBottom()
            
            #Parse CAN into tables
            #Get the message counter for the session 
            #Assignment: add a button that resets the counter.
            self.received_CAN_message_count += 1
            timestamp = time.time() #PC Time
            vda_timestamp = struct.unpack(">L",rxmessage[0:4])[0] # Vehicle Diagnostic Adapter Timestamp 
            extended = rxmessage[4]
            if extended:
                can_id = struct.unpack(">L",rxmessage[5:9])[0]
                databytes = rxmessage[9:]
            else:
                can_id = struct.unpack(">H",rxmessage[5:7])[0]
                databytes = rxmessage[7:]
            dlc = len(databytes)
            
            if (can_id & 0xFF0000) == 0xEC0000:
                if rxmessage[-3] == 0xEC and rxmessage[-2] == 0xFE:
                    print("Found a transport layer connection management message for VIN")
                    message_text = ""
                    for b in rxmessage:
                        message_text+="{:02X} ".format(b)
                    print(message_text)
            #Insert a new row:
            row_count = self.received_CAN_message_table.rowCount()
            self.received_CAN_message_table.insertRow(row_count)
            
            #Populate the row with data
            self.received_CAN_message_table.setItem(row_count,0,
                 QTableWidgetItem("{}".format(self.received_CAN_message_count)))
            
            self.received_CAN_message_table.setItem(row_count,1,
                 QTableWidgetItem("{:0.6f}".format(timestamp)))
            
            self.received_CAN_message_table.setItem(row_count,2,
                 QTableWidgetItem("{:0.3f}".format(vda_timestamp* 0.001))) #Figure out what the multiplier is for the time stamp
            
            self.received_CAN_message_table.setItem(row_count,3,
                 QTableWidgetItem("{:08X}".format(can_id)))
            #Assignment: Make the ID format conditional on 29 or 11 bit IDs
            
            self.received_CAN_message_table.setItem(row_count,4,
                 QTableWidgetItem("{}".format(dlc)))
            
            col=5
            for b in databytes:
                self.received_CAN_message_table.setItem(row_count,col,
                    QTableWidgetItem("{:02X}".format(b)))
                col+=1

            if self.received_CAN_message_count < 100:
                self.received_CAN_message_table.resizeColumnsToContents()

    def show_about_dialog(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("TU-RP1210 Application")
        msg.setInformativeText("""Icons by Icons8\nhttps://icons8.com/""")
        msg.setWindowTitle("About")
        msg.setDetailedText("There will be some details here.")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setWindowModality(Qt.ApplicationModal)
        msg.exec_()

    def get_hardware_status_ex(self):
        message_window = QMessageBox()
        message_window.setIcon(QMessageBox.Information)
        message_window.setWindowTitle('RP1210 Extended Hardware Status')
        message_window.setStandardButtons(QMessageBox.Ok)

        if self.RP1210.GetHardwareStatusEx is None or self.RP1210.nClientID is None:
            message = "RP1210_GetHardwareStatusEx() function is not available."
        else:
            nClientID = self.RP1210.nClientID
            fpchClientInfo = (c_char*256)()
           
            #There is no return value for RP1210_ReadVersion
            return_value = self.RP1210.GetHardwareStatusEx(c_short(nClientID),
                                                         byref(fpchClientInfo))
            if return_value == 0 :
                message = ""
                status_bytes = fpchClientInfo.raw
                print(status_bytes)
                
                
                hw_device_located = (status_bytes[0] & 0x01) >> 0
                if hw_device_located:
                    message += "The hardware device was located and it is ready.\n"
                else:
                    message += "The hardware device was not located.\n"
                
                hw_device_internal = (status_bytes[0] & 0x02) >> 1
                if hw_device_internal:
                    message += "The hardware device is an internal device, non-wireless.\n"
                else:
                    message += "The hardware device is not an internal device, non-wireless.\n"
                
                hw_device_external = (status_bytes[0] & 0x04) >> 2
                if hw_device_external:
                    message += "The hardware device is an external device, non-wireless.\n"
                else:
                    message += "The hardware device is not an external device, non-wireless.\n"
                
                hw_device_internal = (status_bytes[0] & 0x08) >> 3
                if hw_device_internal:
                    message += "The hardware device is an internal device, wireless.\n"
                else:
                    message += "The hardware device is not an internal device, wireless.\n"
                
                hw_device_external = (status_bytes[0] & 0x10) >> 4
                if hw_device_external:
                    message += "The hardware device is an external device, wireless.\n"
                else:
                    message += "The hardware device is not an external device, wireless.\n"
                
                auto_baud = (status_bytes[0] & 0x20) >> 5
                if auto_baud:
                    message += "The hardware device CAN auto-baud capable.\n"
                else:
                    message += "The hardware device is not CAN auto-baud capable.\n"
                
                number_of_clients = status_bytes[1]
                message += "The number of connected clients is {}.\n\n".format(number_of_clients)
                
                number_of_can = status_bytes[1]
                message += "The number of simultaneous CAN channels is {}.\n\n".format(number_of_can)
                
                message += "There may be more information available than what is currently shown."
            else: 
                if return_value in RP1210Errors:
                    message = "RP1210_GetHardwareStatusEx failed with a return value of  {}: {}".format(return_value,RP1210Errors[return_value])
                else:
                    message = "RP1210_GetHardwareStatusEx failed with\nan unknown error. Code: {}".format(return_value)
        
        print(message)
        message_window.setText(message)
        message_window.exec_()

    def get_hardware_status(self):
        message_window = QMessageBox()
        message_window.setIcon(QMessageBox.Information)
        message_window.setWindowTitle('RP1210 Hardware Status')
        message_window.setStandardButtons(QMessageBox.Ok)

        if self.RP1210.GetHardwareStatus is None or self.RP1210.nClientID is None:
            message = "RP1210_GetHardwareStatus() function is not available."
            message_window.setText(message)
            
        else:
            nClientID = self.RP1210.nClientID
            fpchClientInfo = (c_char*64)()
            nInfoSize = 64
           
            #There is no return value for RP1210_ReadVersion
            return_value = self.RP1210.GetHardwareStatus(c_short(nClientID),
                                                         byref(fpchClientInfo),
                                                         c_short(nInfoSize),
                                                         c_short(NON_BLOCKING_IO))
            if return_value == 0 :
                message = ""
                status_bytes = fpchClientInfo.raw
                print(status_bytes)
                
                
                hw_device_located = (status_bytes[0] & 0x01) >> 0
                if hw_device_located:
                    message += "The hardware device was located.\n"
                else:
                    message += "The hardware device was not located.\n"
                
                hw_device_internal = (status_bytes[0] & 0x02) >> 1
                if hw_device_internal:
                    message += "The hardware device is an internal device.\n"
                else:
                    message += "The hardware device is not an internal device.\n"
                
                hw_device_external = (status_bytes[0] & 0x04) >> 2
                if hw_device_external:
                    message += "The hardware device is an external device.\n"
                else:
                    message += "The hardware device is not an external device.\n"
                
                number_of_clients = status_bytes[1]
                message += "The number of connected clients is {}.\n\n".format(number_of_clients)
            
                    
                j1939_active = (status_bytes[2] & 0x01) >> 0
                if j1939_active:
                    message += "The J1939 link is activated.\n"
                else:
                    message += "The J1939 link is not activated.\n"

                traffic_detected = (status_bytes[2] & 0x02) >> 1
                if traffic_detected:
                    message += "J1939 network traffic was detected in the last second.\n"
                else:
                    message += "J1939 network traffic was not detected in the last second.\n"

                bus_off = (status_bytes[2] & 0x04) >> 2
                if bus_off:
                    message += "The CAN controller reports a BUS_OFF status.\n"
                else:
                    message += "The CAN controller does not report a BUS_OFF status.\n"
                number_of_clients = status_bytes[3]
                message += "The number of clients connected to J1939 is {}.\n\n".format(number_of_clients)
                
                
                j1708_active = (status_bytes[4] & 0x01) >> 0
                if j1708_active:
                    message += "The J1708 link is activated.\n"
                else:
                    message += "The J1708 link is not activated.\n"

                traffic_detected = (status_bytes[4] & 0x02) >> 1
                if traffic_detected:
                    message += "J1708 network traffic was detected in the last second.\n"
                else:
                    message += "J1708 network traffic was not detected in the last second.\n"

                number_of_clients = status_bytes[5]
                message += "The number of clients connected to J1708 is {}.\n\n".format(number_of_clients)
                
                can_active = (status_bytes[6] & 0x01) >> 0
                if can_active:
                    message += "The CAN link is activated.\n"
                else:
                    message += "The CAN link is not activated.\n"

                traffic_detected = (status_bytes[6] & 0x02) >> 1
                if traffic_detected:
                    message += "CAN network traffic was detected in the last second.\n"
                else:
                    message += "CAN network traffic was not detected in the last second.\n"

                bus_off = (status_bytes[6] & 0x04) >> 2
                if bus_off:
                    message += "The CAN controller reports a BUS_OFF status.\n"
                else:
                    message += "The CAN controller does not report a BUS_OFF status.\n"
                number_of_clients = status_bytes[7]
                message += "The number of clients connected to CAN is {}.\n\n".format(number_of_clients)

                j1850_active = (status_bytes[8] & 0x01) >> 0
                if j1850_active:
                    message += "The J1850 link is activated.\n"
                else:
                    message += "The J1850 link is not activated.\n"

                traffic_detected = (status_bytes[8] & 0x02) >> 1
                if traffic_detected:
                    message += "J1850 network traffic was detected in the last second.\n"
                else:
                    message += "J1850 network traffic was not detected in the last second.\n"

                number_of_clients = status_bytes[9]
                message += "The number of clients connected to J1850 is {}.\n\n".format(number_of_clients)

                iso_active = (status_bytes[16] & 0x01) >> 0
                if iso_active:
                    message += "The ISO15765 link is activated.\n"
                else:
                    message += "The ISO15765 link is not activated.\n"

                traffic_detected = (status_bytes[16] & 0x02) >> 1
                if traffic_detected:
                    message += "ISO15765 network traffic was detected in the last second.\n"
                else:
                    message += "ISO15765 network traffic was not detected in the last second.\n"

                bus_off = (status_bytes[16] & 0x04) >> 2
                if bus_off:
                    message += "The CAN controller reports a BUS_OFF status.\n"
                else:
                    message += "The CAN controller does not report a BUS_OFF status.\n"
                number_of_clients = status_bytes[17]
                message += "The number of clients connected to ISO15765 is {}.\n\n".format(number_of_clients)


            else: 
                if return_value in RP1210Errors:
                    message = "RP1210_GetHardwareStatus failed with a return value of  {}: {}".format(return_value,RP1210Errors[return_value])
                else:
                    message = "RP1210_GetHardwareStatus failed with\nan unknown error. Code: {}".format(return_value)
        
        print(message)
        message_window.setText(message)
        message_window.exec_()

    def display_version(self):

        message_window = QMessageBox()
        message_window.setIcon(QMessageBox.Information)
        message_window.setWindowTitle('RP1210 Version Information')
        message_window.setStandardButtons(QMessageBox.Ok)

        if self.RP1210.ReadVersion is None or self.RP1210.nClientID is None:
            message_window.setText("RP1210_ReadVersion() function is not available.")
            print("RP1210_ReadVersion() is not supported.")
        else:        
            chDLLMajorVersion    = (c_char)()
            chDLLMinorVersion    = (c_char)()
            chAPIMajorVersion    = (c_char)()
            chAPIMinorVersion    = (c_char)()

            #There is no return value for RP1210_ReadVersion
            self.RP1210.ReadVersion(byref(chDLLMajorVersion), 
                                    byref(chDLLMinorVersion), 
                                    byref(chAPIMajorVersion), 
                                    byref(chAPIMinorVersion))
            print('Successfully Read DLL and API Versions.')
            DLLMajor = chDLLMajorVersion.value.decode('ascii','ignore')
            DLLMinor = chDLLMinorVersion.value.decode('ascii','ignore')
            APIMajor = chAPIMajorVersion.value.decode('ascii','ignore')
            APIMinor = chAPIMinorVersion.value.decode('ascii','ignore')
            print("DLL Major Version: {}".format(DLLMajor))
            print("DLL Minor Version: {}".format(DLLMinor))
            print("API Major Version: {}".format(APIMajor))
            print("API Minor Version: {}".format(APIMinor))
            message_window.setText("Driver software versions are as follows:\nDLL Major Version: {}\nDLL Minor Version: {}\nAPI Major Version: {}\nAPI Minor Version: {}".format(DLLMajor,DLLMinor,APIMajor,APIMinor))
        message_window.exec_()
    
    def get_last_error_msg(self):

        nErrorCode, ok = QInputDialog.getInt(self, 'Last Error Code','Enter Error Code:',value = -1,min = 0,max=255)

        message_window = QMessageBox()
        message_window.setIcon(QMessageBox.Information)
        message_window.setWindowTitle('RP1210 Get Last Error Message')
        message_window.setStandardButtons(QMessageBox.Ok)
        # Make sure the function prototype is available:
        if self.RP1210.GetLastErrorMsg is not None and self.RP1210.nClientID is not None:
            clientID = int(self.RP1210.nClientID)
            fpchDescription = (c_char*80)()
            nSubErrorCode = (c_int)()
            return_value = self.RP1210.GetLastErrorMsg(c_short(nErrorCode),
                                                       byref(nSubErrorCode),
                                                       byref(fpchDescription),
                                                       c_short(clientID))
            description = fpchDescription.value.decode('ascii','ignore')
            sub_error = nSubErrorCode.value
            if return_value == 0 :
                message = "Client ID is {}.\nError Code {} means {}".format(clientID, nErrorCode, description)
                if sub_error < 0:
                    message_window.setInformativeText("No subordinate error code is available.")
                else:
                    message_window.setInformativeText("Additional Code: {}".format(sub_error))
            else: 
                if return_value in RP1210Errors:
                    message = "RP1210_GetLastErrorMsg failed with\na return value of  {}: {}".format(return_value,RP1210Errors[return_value])
                else:
                    message = "RP1210_GetLastErrorMsg failed with\nan unknown error. Code: {}".format(return_value)          
        else:
            message = "RP1210_GetLastErrorMsg() function is not available."
        
        print(message)
        message_window.setText(message)
        message_window.exec_()

    def get_error_code(self,code):
        # Make sure the function prototype is available:
        if self.RP1210.GetErrorMsg is not None:
            #make sure the error code is an integer
            try:
                code = int(code)
            except Exception as e:
                print(e)
                code = -1
            # Set up the decription buffer
            fpchDescription = (c_char*80)()
            return_value = self.RP1210.GetErrorMsg(c_short(code),
                                                   byref(fpchDescription))
            description = fpchDescription.raw.decode('ascii','ignore')
            
            if return_value == 0:
               return description
            else: 
                if return_value in RP1210Errors:
                    print("RP1210_GetErrorMsg failed with a return value of  {}: {}".format(return_value,RP1210Errors[return_value]))
                    return "RP1210_GetErrorMsg failed with a return value of  {}: {}".format(return_value,RP1210Errors[return_value])
                else:
                    return "RP1210_GetErrorMsg failed with an unknown error. Code: {}".format(return_value)
        else:
            return "Error code interpretation not available."
        message_window.exec_()

    def lookup_error_code(self):
        """This functions returns the textual description of the error code returned by a routine."""
        nErrorCode, ok = QInputDialog.getInt(self, 'Error Code','Enter Error Code:',value = -1,min = 0,max=255)
        if ok:
            message_window = QMessageBox()
            message_window.setIcon(QMessageBox.Information)
            message_window.setWindowTitle('RP1210 Get Error Message')
            message_window.setStandardButtons(QMessageBox.Ok)

            if self.RP1210.GetErrorMsg is None:
                print("RP1210_GetErrorMsg() is not available.")
                message_window.setText("RP1210_GetErrorMsg() function is not available.")
            else:
                
                fpchDescription = (c_char*80)()
                return_value = self.RP1210.GetErrorMsg(c_short(nErrorCode),
                                                       byref(fpchDescription))
                code = nErrorCode #.decode('ascii',ignore)
                description = fpchDescription.raw.decode('ascii','ignore')
                if return_value == 0 :
                   message = "Error Code {} means {}".format(code, description)
                   print(message)
                   message_window.setText(message)
                else: 
                    if return_value in RP1210Errors:
                        print("RP1210_GetErrorMsg failed with a return value of  {}: {}".format(return_value,RP1210Errors[return_value]))
                        message_window.setText("RP1210_GetErrorMsg failed with\na return value of  {}: {}".format(return_value,RP1210Errors[return_value]))
                    else:
                        message_window.setText("RP1210_GetErrorMsg failed with\nan unknown error. Code: {}".format(return_value))           
            message_window.exec_()

    def display_detailed_version(self):
        message_window = QMessageBox()
        message_window.setIcon(QMessageBox.Information)
        message_window.setWindowTitle('RP1210 Detailed Version')
        message_window.setStandardButtons(QMessageBox.Ok)
            
        if self.RP1210.ReadDetailedVersion is None or self.RP1210.nClientID is None:
            message = "RP1210_ReadDetailedVersion() function is not available."
        else:
            chAPIVersionInfo    = (c_char*17)()
            chDLLVersionInfo    = (c_char*17)()
            chFWVersionInfo     = (c_char*17)()
            return_value = self.RP1210.ReadDetailedVersion(c_short(self.RP1210.nClientID), 
                                                        byref(chAPIVersionInfo),
                                                        byref(chDLLVersionInfo), 
                                                        byref(chFWVersionInfo))
            if return_value == 0 :
                message = 'The PC computer has successfully connected to the RP1210 Device.\nThere is no need to check your USB connection.\n'
                DLL = chDLLVersionInfo.value
                API = chAPIVersionInfo.value
                FW = chAPIVersionInfo.value
                message += "DLL = {}\n".format(DLL.decode('ascii','ignore'))
                message += "API = {}\n".format(API.decode('ascii','ignore'))
                message += "FW  = {}".format(FW.decode('ascii','ignore'))
            else: 
                if return_value in RP1210Errors:
                    message = "RP1210_ReadDetailedVersion failed with\na return value of  {}: {}".format(return_value,RP1210Errors[return_value])
                else:
                    message = "RP1210_ReadDetailedVersion failed with\nan unknown error. Code: {}".format(return_value)          
        message_window.setText(message)
        message_window.exec_()

    def disconnectRP1210(self):
        nClientID = self.RP1210.nClientID
        if nClientID is not None:
            # Many RP1210 devices can handle 16 clients, so lets close all of those down.
            # TODO, keep track of the actual clients connected.
            for n in range(16,1,-1): 
                try:
                    return_value = self.RP1210.ClientDisconnect(n)
                    message = "RP1210_ClientDisconnect returns {}: {}".format(return_value,RP1210Errors[return_value])
                except Exception as e:
                    print(e)
                    message = "There was an exception with RP1210.ClientDisconnect({})".format(n)
                print(message)
                self.statusBar().showMessage(message)
        else:
            print("nClientID is ", end='')
            print(nClientID)

    def closeEvent(self, *args, **kwargs):
        self.disconnectRP1210()
        print("Exiting")

if __name__ == '__main__':
    app = QCoreApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    else:
        app.close()
    execute = TUDiagnostics()
    sys.exit(app.exec_())