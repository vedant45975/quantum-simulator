from glob import glob
import sys, random, os
from unittest import skip
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QLabel
from matplotlib.figure import Figure
from PIL import Image
from threading import *
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5 import QtCore, QtGui, QtWidgets
import DesignerFile
import numpy as np
from pathlib import Path
import pandas as pd
import tempfile
import DataDiagram
import ParseCircuit
import TensorContractionGeneration
import networkx as nx

# Default X ignore
ignoreX = 4

# Load up all graphic images, Singleton design pattern
gateToImage = {" ": Image.open("./assets/EMPTY.png"), "-": Image.open("./assets/GATE.png"), "H": Image.open("./assets/H.png"), 
                "T": Image.open("./assets/T.png"), "S": Image.open("./assets/S.png"), "X": Image.open("./assets/X.png"), "Y": Image.open("./assets/Y.png"),
                "Z": Image.open("./assets/Z.png"), "CNOT": Image.open("./assets/CNOT.png"),"M": Image.open("./assets/M.png")}

# Same grid information, offSetHorizontal offsets to the play field (where user puts gates)
# from the gate storage and barrier positions
currentWidth = 8
currentHeight = 5
offSetHorizontal = 3

customGates = {}
positionsWithCustomGates = {(-1, -1): "NA"}
undoStack = []
redoStack = []

# Default to the "-" gate, store previous position of barrier
grid = [["-" for i in range(currentWidth + offSetHorizontal)] for j in range(currentHeight)]
priorBarrier = [-1,-1,-1,-1]

# Initalize Designer
designer = DesignerFile.Designer(currentHeight, currentWidth)

# Various graphics settings
hamiltonian = False
needToUpdate = False
photonicMode = False


# Specific global state for cuQuantum
cuQuantumBitStrings = []
cuQuantumGateSplit = 0
cuQuantumConfig = [0,1,2,3]

# GUI for CNOT Gate
class PopupWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Enter Input')
        self.layout = QFormLayout(self)
        self.inputLine_1 = QLineEdit(self)
        self.inputLine_2 = QLineEdit(self)
        self.layout.addRow('Control:', self.inputLine_1)
        self.layout.addRow('Target:', self.inputLine_2)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

    def controlqubit(self):
        return self.inputLine_1.text()
    def targetqubit(self):
        return self.inputLine_2.text()

# For field elements that complete change layout
def forceUpdate():
    global window
    window.close()
    window = Window()
    window.show()


# Cursed as it is, this is a lookup table to store the inital gate positions
def inital(row, col):
    if(photonicMode == False):
        if(row == 0 and col == 0):
            return "H"
        if(row == 0 and col == 1):
            return "X"
        if(row == 1 and col == 0):
            return "Y"
        if(row == 1 and col == 1):
            return "Z"
        if(row == 2 and col == 0):
            return "S"
        if(row == 2 and col == 1):
            return "T"
        if(row == 3 and col == 0):
            return "CNOT"
        if(row == 3 and col == 1):
            return "M"
        if(row == 4 and col == 0):
            if(len(customGates) != 0):
                return list(customGates.keys())[0]
        if(row == 4 and col == 1):
            if(len(customGates) > 1):
                return list(customGates.keys())[1]
        if(row == 5 and col == 0):
            if(len(customGates) > 2):
                return list(customGates.keys())[2]
    return " "


# This runs the simulation
def runSimulation():
    print("---------------------Running Simulation-------------------------------------")
    #DEPENDING upon which BACKEND is selected, the control flow is different [might need other GUI settings]
    print("Quantum Circuit Printout: ")
    global grid
    print("\ngrid",grid)
    numDepth = currentWidth
    numQubits = currentHeight
    entry = ""
    for depth in range(3*(numDepth+1)):
        entry += "-"
    print(entry)
    starredPositions = {(-1,-1)}
    for qubit in range(numQubits):
        tempStr = ""
        nextOne = False
        for depth in range(offSetHorizontal, numDepth):
            if((qubit, depth) in starredPositions):
                tempStr += "[*]"
            else:
                designer.gateAddition(grid[qubit][depth], depth-offSetHorizontal, qubit)
                tempStr += "[" + grid[qubit][depth] + "]"
            if(len(grid[qubit][depth]) >= 3 and "PP" not in grid[qubit][depth]):
                starredPositions.add((qubit + 1, depth))
            tempStr += "[M]"
        print(tempStr)
    print(entry)
    print("------------------------BACKEND GOT-------------------------------------")
    # Have the designer confirm the board (for debugging)
    designer.printDesign()
    # Run the simulation
    designer.runSimulation()
    # Get the output
    plt = designer.getVisualization()
    plt.show()

#changes settingfile based on user choice
def changeSimulationTechniqueQiskit():
    designer.setBackend("Qiskit")
    print("Changed to Qiskit Backend")

# Change Various settings based on click events, self-explanatory
def changeMeasurement(checked):
    designer.settings.measurement = checked
    print("Set measurement to " + str(checked))
def changeSuggestion(checked):
    designer.settings.gate_suggestion = checked
    designer.suggestSimplifications(grid)
    print("Set gate suggestion to " + str(checked))
def changeIncresav(checked):
    designer.settings.incremental_saving = checked
    print("Set incremental saving to " + str(checked))
def changeIncresim(checked):
    designer.settings.incremental_simulation = checked
    print("Set incremental simulation to " + str(checked))
def updateNumQubit(val):
    designer.settings.num_qubits = val
    global currentHeight,grid
    currentHeight = val
    print("Set number of qubits to " + str(val))
    updateDesignerGrid(currentHeight)
def updateDesignerGrid(currentHeight):
    global grid, designer
    grid = [["-" for i in range(currentWidth + offSetHorizontal)] for j in range(currentHeight)]
    # Initalize Designer
    designer = DesignerFile.Designer(currentHeight, currentWidth)
def updateNumBit(val):
    designer.settings.num_bits = val
    print("Set number of bits to " + str(val))

# This is a less forceful update that changes whenever the GUI is interacted with
def updateGrid():
    global grid
    global needToUpdate
    grid = designer.getGUIGrid()
    needToUpdate = True

# Changes Width of Quantum Circuit
def updateNumWidth(val):
    designer.settings.num_width = val
    global currentWidth
    currentWidth = val
    print("Set width to " + str(val))

def dataDiagramVisualization():
    histogram = designer.getStatistics()
    if(type(histogram) == type(list())):
        histogramNew = dict() 
        for entry in histogram:
            histogramNew[entry[0]] = entry[1]
        histogram = histogramNew
    print("Button press for Data Diagram...")
    print(histogram)
    sumHistogram = 0
    lastEntry = ""
    for entry, value in histogram.items():
        sumHistogram += value
        lastEntry = entry
    vector = np.zeros((1, 2**len(entry)))
    for entry, value in histogram.items():
        vector[0][int(entry, 2)] = value/sumHistogram
    print(vector)
    root = DataDiagram.makeDataDiagram(vector[0], 0, False)
    G = nx.Graph()
    def followSelf(root, prior):
        finalValue = prior
        while((root.get_left() != None and str(root) == str(root.get_left())) or (root.get_right() != None and str(root) == str(root.get_right()))):
            if(root.get_left() != None and str(root) == str(root.get_left())):
                if(finalValue > root.get_left().get_amplitude()):
                    finalValue = root.get_left().get_amplitude()
                root = root.get_left()
            if(root.get_right() != None and str(root) == str(root.get_right())):
                if(finalValue > root.get_right().get_amplitude()):
                    finalValue = root.get_right().get_amplitude()
                root = root.get_right()
        return finalValue
    def createGraph(root, parent, G, index=0, level=0):
        if(not G.has_node(str(root))):
            G.add_node(str(root), pos=(index, -level))
        if(str(root) != "DD"):
            if(root != None and root.get_left() != None and str(root) == str(root.get_left())):
                G.add_edge(str(parent), str(root), weight=round(followSelf(root, root.get_left().get_amplitude()),2))
            else:
                if(root != None and root.get_right() != None and str(root) == str(root.get_right())):
                    G.add_edge(str(parent), str(root), weight=round(followSelf(root, root.get_right().get_amplitude()),2))
                else:
                    if(root != None and str(parent) != str(root)):
                        G.add_edge(str(parent), str(root), weight=round(root.get_amplitude(),2))
        if(root != None):
            print("  " * (2*level), root, "| Amplitude: ", root.get_amplitude())
        if(root != None and root.get_left() != None):
            createGraph(root.get_left(), root, G, (index), level + 1)
        if(root != None and root.get_right() != None):
            createGraph(root.get_right(), root, G, (index+1), level + 1)
    createGraph(root, root, G)
    pos=nx.get_node_attributes(G,'pos')
    nx.draw(G,pos,with_labels=True)
    # Currently, the implementation is buggy...to say the least, works with amplitudes, just don't show the user :P
    #labels = nx.get_edge_attributes(G,'weight')
    #nx.draw_networkx_edge_labels(G,pos,edge_labels=labels)
    plt.show()
    
def showParseGrid():
    tempGrid = [["H", "H", "S", "-", "-"], ["CNOT", "*", "-", "-", "-"], ["-", "CNOT", "*", "-", "-"], ["CNOT", "*", "CCX", "*", "*"], ["CCX", "*", "*", "S", "-"], ["S", "-", "-", "-", "-"]]
    print("---------------------------PARSER IMPLEMENTATION IN PROGRESS-------------------------------------")
    for entry in tempGrid:
        print(entry)
    print("---------------------------------LL(1) PARSER---------------------------------------------")
    ParseCircuit.parse(tempGrid)
    
def showTensorNetwork():
    gridA = [["H", "H", "S", "-", "-"], ["CNOT", "*", "-", "-", "-"], ["-", "CNOT", "*", "-", "-"],
        ["CNOT", "*", "CCX", "*", "*"], ["CCX", "*", "*", "S", "-"], ["S", "-", "-", "-", "-"]]
    gridB = [["H", "H", "H", "H"], ["CX", "*", "X(1/2)", "T"], ["X(1/2)", "CX", "*", "Y(1/2)"], ["T", "X(1/2)", "CX", "*"], ["CX", "-", "-", "*"], ["H", "H", "H", "H"]]
    print("---------------------------PARSER IMPLEMENTATION IN PROGRESS-------------------------------------")
    if(random.random() >= 0.5):
        print("EXAMPLE NETWORK 1: (GRID A)")
        array = np.array(gridA)
        transposed_array = array.T
        transposed_list_of_lists = transposed_array.tolist()
        for entry in transposed_list_of_lists:
            print(entry)
        print("---------------------------------------------------")
        tree = TensorContractionGeneration.parse(gridA)
        layers = TensorContractionGeneration.getComputationLayers(tree)
        G = TensorContractionGeneration.generateTensorNetworkGraph(layers, 5)
        TensorContractionGeneration.drawTensorNetworkGraph(G)
        plt.show()
    else:
        print("EXAMPLE NETWORK 2: (GRID B)")
        array = np.array(gridB)
        transposed_array = array.T
        transposed_list_of_lists = transposed_array.tolist()
        for entry in transposed_list_of_lists:
            print(entry)
        print("---------------------------------------------------")
        tree = TensorContractionGeneration.parse(gridB)
        layers = TensorContractionGeneration.getComputationLayers(tree)
        G = TensorContractionGeneration.generateTensorNetworkGraph(layers, 4)
        TensorContractionGeneration.drawTensorNetworkGraph(G)
        plt.show()


#the main workbench of qcd, a grid that supports drag & drop
class IndicSelectWindow(QDialog):
    def __init__(self, parent=None):
        super(IndicSelectWindow, self).__init__(parent=parent)
        self.resize(3000, 1200)
        self.target = None
        self.setAcceptDrops(True)
        self.layout = QHBoxLayout(self)
        self.scrollArea = QScrollArea(self)
        self.scrollArea.setWidgetResizable(True)
        self.scrollAreaWidgetContents = QWidget()
        self.gridLayout = QGridLayout(self.scrollAreaWidgetContents)
        self.scrollArea.setWidget(self.scrollAreaWidgetContents)
        self.layout.addWidget(self.scrollArea)

        # Go through the grid and initalize values
        skipThis = [-1, -1] # For multiqubit gates, skip initalizing covered positions
        for j in range(1, offSetHorizontal + 1):
            for i in range(currentHeight):
                if(skipThis[0] == i and skipThis[1] == j):
                    grid[i][j - 1] = " "
                    break
                grid[i][j-1] = " "
                self.Frame = QFrame(self)
                self.Frame.setStyleSheet("background-color: white;")
                self.Frame.setFrameStyle(QFrame.Panel | QFrame.Raised)
                self.Frame.setLineWidth(0)
                self.layout = QHBoxLayout(self.Frame)

                self.figure = Figure()  # a figure to plot on
                self.canvas = FigureCanvas(self.figure)
                self.ax = self.figure.add_subplot(111)  # create an axis
                if(j == offSetHorizontal):  # If we need to create the barrier
                    self.Frame.setStyleSheet("background-color: grey;")
                    Box = QVBoxLayout()
                    Box.addWidget(self.Frame)
                    self.gridLayout.addLayout(Box, i, j-1, len(grid)-2, 1)
                    global priorBarrier
                    priorBarrier = [i, j - 1, len(grid)-2, 1]
                else: # If we are adding just a gate
                    global customGates
                    grid[i][j - 1] = inital(i, j - 1) # Find what gate if any should go in position
                    if(grid[i][j - 1] in customGates):
                        self.ax.text(0.5, 0.5, grid[i][j - 1], horizontalalignment='center', verticalalignment='center', transform=self.ax.transAxes)
                    else:
                        self.ax.imshow(gateToImage[grid[i][j - 1]]) # Show the gate
                    self.ax.set_axis_off()
                    self.canvas.draw()  # refresh canvas
                    self.layout.addWidget(self.canvas)
                    self.canvas.installEventFilter(self)
                    Box = QVBoxLayout()
                    Box.addWidget(self.Frame)
                    self.gridLayout.addLayout(Box, i, j - 1)
        # Go through and initalize field user interacts with
        for i in range(offSetHorizontal, currentWidth + offSetHorizontal):
            for j in range(currentHeight):
                grid[j][i] = "-"
                self.Frame = QFrame(self)
                self.Frame.setStyleSheet("background-color: white;")
                self.Frame.setLineWidth(0)
                self.layout = QHBoxLayout(self.Frame)

                self.figure = Figure()  # a figure to plot on
                self.canvas = FigureCanvas(self.figure)
                self.ax = self.figure.add_subplot(111)  # create an axis
                self.ax.imshow(gateToImage["-"])
                self.ax.set_axis_off()
                self.canvas.draw()  # refresh canvas
                self.canvas.installEventFilter(self)

                self.layout.addWidget(self.canvas)

                Box = QVBoxLayout()

                Box.addWidget(self.Frame)

                self.gridLayout.addLayout(Box, j, i)

    # Run fo the mill event filter
    def eventFilter(self, watched, event):
        if event.type() == QEvent.MouseButtonPress:
            self.mousePressEvent(event)
        elif event.type() == QEvent.MouseMove:
            self.mouseMoveEvent(event)
        elif event.type() == QEvent.MouseButtonRelease:
            self.mouseReleaseEvent(event)
        return super().eventFilter(watched, event)

    # Allow easy access to grid index from gridLayout position
    def get_index(self, pos):
        for i in range(self.gridLayout.count()):
            if self.gridLayout.itemAt(i).geometry().contains(pos) and i != self.target:
                return i

    # Load up source information if user clicks a gate
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.target = self.get_index(event.windowPos().toPoint())
        else:
            self.Frame = QFrame(self)
            self.Frame.setStyleSheet("background-color: white;")
            self.Frame.setFrameStyle(QFrame.Panel | QFrame.Raised)
            self.Frame.setLineWidth(0)
            self.layout = QHBoxLayout(self.Frame)

            self.figure = Figure()  # a figure to plot on
            self.canvas = FigureCanvas(self.figure)
            self.ax = self.figure.add_subplot(111)  # create an axis
            row, col, _, _ = self.gridLayout.getItemPosition(self.get_index(event.windowPos().toPoint()))
            self.ax.imshow(grid[row][col])
            self.canvas.draw()  # refresh canvas
            self.canvas.installEventFilter(self)

            self.layout.addWidget(self.canvas)

            Box = QVBoxLayout()

            Box.addWidget(self.Frame)

            self.gridLayout.addLayout(Box, 0, 6)
            self.gridLayout.setColumnStretch(6, 1)
            self.gridLayout.setRowStretch(0, 1)

    # If moving the mouse, bring the element with you
    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self.target is not None:
            drag = QDrag(self.gridLayout.itemAt(self.target))
            pix = self.gridLayout.itemAt(self.target).itemAt(0).widget().grab()
            mimedata = QMimeData()
            mimedata.setImageData(pix)
            drag.setMimeData(mimedata)
            drag.setPixmap(pix)
            drag.setHotSpot(event.pos())
            drag.exec_()
        global needToUpdate
        global grid
        global positionsWithCustomGates
        # If we need to update the grid, update all positions to have GUI be consistent with Grid 2D array
        if needToUpdate:
            print("Updating....")
            needToUpdate = False
            skipThis = [-1, -1]
            skip = {(-1, -1)}
            for i in range(offSetHorizontal, currentWidth + offSetHorizontal):
                for j in range(currentHeight):
                    self.Frame = QFrame(self)
                    self.Frame.setStyleSheet("background-color: white;")
                    self.Frame.setLineWidth(0)
                    self.layout = QHBoxLayout(self.Frame)

                    self.figure = Figure()  # a figure to plot on
                    self.canvas = FigureCanvas(self.figure)
                    self.ax = self.figure.add_subplot(111)  # create an axis
                    if((j, i) not in positionsWithCustomGates and (j, i) not in skip):
                        if (grid[j][i] not in customGates):
                            self.ax.imshow(gateToImage[grid[j][i]])
                        else:
                            self.ax.text(0.5, 0.5, grid[j][i], horizontalalignment='center', verticalalignment='center', transform=self.ax.transAxes)
                        self.ax.set_axis_off()
                        self.canvas.draw()  # refresh canvas
                        self.canvas.installEventFilter(self)
                        self.layout.addWidget(self.canvas)
                        Box = QVBoxLayout()
                        Box.addWidget(self.Frame)
                        self.gridLayout.removeItem(self.gridLayout.itemAtPosition(j, i))
                        self.gridLayout.addLayout(Box, j, i)
                    else:
                        if((j, i) not in skip):
                            name = positionsWithCustomGates[(j, i)]
                            self.ax.set_axis_off()
                            self.canvas.draw()  # refresh canvas
                            self.canvas.installEventFilter(self)
                            self.layout.addWidget(self.canvas)
                            Box = QVBoxLayout()
                            Box.addWidget(self.Frame)
                            self.gridLayout.addLayout(Box, j, i, len(customGates[name][0]), len(customGates[name][1]))
                            for x in range(len(customGates[name][0])):
                                for y in range(len(customGates[name][1])):
                                    skip.add((j + x, i + y))
                                    self.gridLayout.removeItem(self.gridLayout.itemAtPosition(j + x, i + y))

    # If releasing, event on drag and drop occured, so neglect this gate
    def mouseReleaseEvent(self, event):
        self.target = None

    # Only allow gates to be draggable elements
    def dragEnterEvent(self, event):
        if event.mimeData().hasImage():
            event.accept()
        else:
            event.ignore()

    # Handle drop logic
    def dropEvent(self, event):
        if not event.source().geometry().contains(event.pos()):
            source = self.get_index(event.pos())
            if source is None:
                return
            # Get source and destination points
            i, j = max(self.target, source), min(self.target, source)
            row, col, _, _ = self.gridLayout.getItemPosition(self.target)
            row2, col2, _, _ = self.gridLayout.getItemPosition(source)
            global positionsWithCustomGates
            global customGates
            # If it is a photonic gate, get necessary values for gate specification
            global photonicMode
            if (photonicMode == True):
                val1, val2 = 0.0, 0.0
                val1 = QtWidgets.QInputDialog.getDouble(self, 'First Gate Argument', 'Input:')[0]
                val2 = QtWidgets.QInputDialog.getDouble(self, 'Second Gate Argument', 'Input:')[0]
                global designer
                global offSetHorizontal
                # Specify the gate properties
                designer.settings.specialGridSettings[(col2-offSetHorizontal,row2)] = [val1, val2]
                print(designer.settings.specialGridSettings)

            p1, p2 = self.gridLayout.getItemPosition(self.target), self.gridLayout.getItemPosition(source)
            # If we are moving a point on the user board, replace positions
            if(self.gridLayout.getItemPosition(self.target)[1] < offSetHorizontal):
                designer.giveGUIGrid(grid)
                f = tempfile.NamedTemporaryFile(delete=False)
                designer.saveSimulationToFile(f.name)
                undoStack.append(f.name)
                f.close()
                self.Frame = QFrame(self)
                self.Frame.setStyleSheet("background-color: white;")
                self.Frame.setLineWidth(0)
                self.layout = QHBoxLayout(self.Frame)
                self.figure = Figure()  # a figure to plot on
                self.canvas = FigureCanvas(self.figure)
                self.ax = self.figure.add_subplot(111)  # create an axis
                isCustom = False
                if(inital(row, col) not in customGates):
                    self.ax.imshow(gateToImage[inital(row, col)])
                else:
                    self.ax.text(0.5, 0.5, inital(row, col), horizontalalignment='center', verticalalignment='center', transform=self.ax.transAxes)
                    isCustom = True
                    print("Dropped Custom (Drag and Drop)")
                if((row, col) in positionsWithCustomGates):
                    isCustom = True
                    grid[row][col]
                self.ax.set_axis_off()
                self.canvas.draw()  # refresh canvas
                self.canvas.installEventFilter(self)
                self.layout.addWidget(self.canvas)
                Box = QVBoxLayout()
                Box.addWidget(self.Frame)
                self.gridLayout.takeAt(source)
                if(isCustom):
                    print("Calling updateGUILayout")
                    grid[row2][col2] = grid[row][col]
                    self.updateGUILayout()
                else:
                    self.gridLayout.addLayout(Box, row2, col2) #row2, col2
                    grid[row2][col2] = grid[row][col]
            else: # Else, ONLY move the gate in the user board
                isCustom = False
                if((row, col) in positionsWithCustomGates):
                    name = positionsWithCustomGates[(row, col)]
                    for x in range(len(customGates[name][0])):
                        for y in range(len(customGates[name][1])):
                            grid[row + x][col + y] = "-"
                            self.gridLayout.removeItem(self.gridLayout.itemAtPosition(row + x, col + y))
                    grid[row][col] = name
                    self.gridLayout.removeItem(self.gridLayout.itemAtPosition(row, col))
                    del positionsWithCustomGates[(row, col)]
                    isCustom = True
                if((row2, col2) in positionsWithCustomGates):
                    name = positionsWithCustomGates[(row2, col2)]
                    for x in range(len(customGates[name][0])):
                        for y in range(len(customGates[name][1])):
                            grid[row2 + x][col2 + y] = "-"
                            self.gridLayout.removeItem(self.gridLayout.itemAtPosition(row2 + x, col2 + y))
                    grid[row2][col2] = name
                    self.gridLayout.removeItem(self.gridLayout.itemAtPosition(row2, col2))
                    del positionsWithCustomGates[(row2, col2)]
                    isCustom = True
                grid[row][col], grid[row2][col2] = grid[row2][col2], grid[row][col]
                if(isCustom):
                    print("Calling updateGUILayout")
                    self.canvas.draw()
                    self.updateGUILayout()
                else:
                    tempA = self.gridLayout.itemAtPosition(row, col)
                    tempB = self.gridLayout.itemAtPosition(row2, col2)
                    self.gridLayout.removeItem(self.gridLayout.itemAtPosition(row, col))
                    self.gridLayout.removeItem(self.gridLayout.itemAtPosition(row2, col2))
                    self.gridLayout.addItem(tempA, *p2)
                    self.gridLayout.addItem(tempB, *p1)

            # Print out the grid (for debugging purposes)
            print("Quantum Circuit Printout:")
            print(grid)
            numDepth = currentWidth
            numQubits = currentHeight
            entry = ""
            for depth in range(3*(numDepth+1)):
                entry += "-"
            print(entry)
            starredPositions = {(-1,-1)}
            for qubit in range(numQubits):
                tempStr = ""
                nextOne = False
                for depth in range(offSetHorizontal, numDepth + offSetHorizontal):
                    if((qubit, depth) in starredPositions):
                        tempStr += "[*]"
                    else:
                        tempStr += "[" + grid[qubit][depth] + "]"
                    if(len(grid[qubit][depth]) >= 3 and "PP" not in grid[qubit][depth]):
                        starredPositions.add((qubit + 1, depth))
                tempStr += "[M]"
                print(tempStr)
            print(entry)

    #update layout basesd on designer class' grid
    def updateGUILayout(self):
        global priorBarrier
        global offSetHorizontal
        global grid
        global currentHeight
        global customGates
        global positionsWithCustomGates
        global currentWidth
        # Basically a repeat from GUI initalization, see those comments for explainations
        skipThis = [-1, -1]
        print("Is this it?")
        for j in range(1, offSetHorizontal + 1):
            for i in range(currentHeight):
                if(skipThis[0] == i and skipThis[1] == j):
                    grid[i][j - 1] = "-"
                    break
                grid[i][j-1] = "-"
                self.Frame = QFrame(self)
                self.Frame.setStyleSheet("background-color: white;")
                self.Frame.setFrameStyle(QFrame.Panel | QFrame.Raised)
                self.Frame.setLineWidth(0)
                self.layout = QHBoxLayout(self.Frame)

                self.figure = Figure()  # a figure to plot on
                self.canvas = FigureCanvas(self.figure)
                self.ax = self.figure.add_subplot(111)  # create an axis
                if(j == offSetHorizontal):
                    self.Frame.setStyleSheet("background-color: grey;")
                    Box = QVBoxLayout()
                    Box.addWidget(self.Frame)
                    self.gridLayout.addLayout(Box, i, j-1, len(grid)-2, 1)
                    priorBarrier = [i, j-1, len(grid)-2, 1]
                else:
                    grid[i][j - 1] = inital(i, j - 1)
                    if(grid[i][j - 1] not in customGates):
                        self.ax.imshow(gateToImage[grid[i][j - 1]])
                    else:
                        self.ax.text(0.5, 0.5, grid[j][i-1], horizontalalignment='center', verticalalignment='center',transform=self.ax.transAxes)
                    self.ax.set_axis_off()
                    self.canvas.draw()  # refresh canvas
                    self.layout.addWidget(self.canvas)
                    self.canvas.installEventFilter(self)
                    Box = QVBoxLayout()
                    Box.addWidget(self.Frame)
                    self.gridLayout.addLayout(Box, i, j - 1)
        skip = []
        for i in range(offSetHorizontal, currentWidth + offSetHorizontal):
            for j in range(currentHeight):
                self.Frame = QFrame(self)
                self.Frame.setStyleSheet("background-color: white;")
                self.Frame.setLineWidth(0)
                self.layout = QHBoxLayout(self.Frame)

                self.figure = Figure()  # a figure to plot on
                self.canvas = FigureCanvas(self.figure)
                self.ax = self.figure.add_subplot(111)  # create an axis
                isCustom = False
                name = "NA"
                if(grid[j][i] not in customGates and (j, i) not in positionsWithCustomGates):
                    self.ax.imshow(gateToImage[grid[j][i]])
                else:
                    if((j, i) not in positionsWithCustomGates):
                        self.Frame.setStyleSheet("background-color: black;")
                        self.ax.text(0.2, 0.75, grid[j][i], horizontalalignment='center', verticalalignment='center', transform=self.ax.transAxes)
                        self.ax.imshow(gateToImage[" "])
                        isCustom = True
                        print("Custom Detected")
                        name = grid[j][i]
                    else:
                        name = positionsWithCustomGates[(j, i)]
                        for x in range(len(customGates[name][0])):
                            for y in range(len(customGates[name][1])):
                                skip.append((j + x, i + y))
                                self.gridLayout.removeItem(self.gridLayout.itemAtPosition(j + x, i + y))
                        self.gridLayout.addLayout(Box, j, i, len(customGates[name][0]), len(customGates[name][1]))
                if((j, i) in skip):
                    self.ax.imshow(gateToImage[" "])
                    self.Frame.setStyleSheet("background-color: black;")
                self.ax.set_axis_off()
                self.canvas.draw()  # refresh canvas
                self.canvas.installEventFilter(self)
                self.layout.addWidget(self.canvas)
                Box = QVBoxLayout()
                Box.addWidget(self.Frame)
                if(not isCustom):
                    self.gridLayout.addLayout(Box, j, i)
                else:
                    self.gridLayout.addLayout(Box, j, i, len(customGates[name][0]), len(customGates[name][1]))
                    for x in range(len(customGates[name][0])):
                        for y in range(len(customGates[name][1])):
                            grid[j+x][i+y] = (customGates[name])[x][y]
                            skip.append((j+x, i+y))
                    positionsWithCustomGates[(j, i)] = name
        print("UPDATED-------------------")


#the main window for display
class Window(QMainWindow):
    def __init__(self, parent=None):
        super(Window, self).__init__(parent)

        self.grid = IndicSelectWindow()
        self.originalPalette = QApplication.palette()

        background = QComboBox()
        background.addItems(QStyleFactory.keys())

        #top menu bar for operations
        menu = self.menuBar()
        file_menu = QMenu("&File", self)
        menu.addMenu(file_menu)
        button_class = QMenu("&Class", self)
        menu.addMenu(button_class)
        button_learn = QMenu("&Learn", self)
        menu.addMenu(button_learn)

        button_exit = QAction("&Exit", self)
        menu.addAction(button_exit)
        #additional exit button (why not)
        button_exit.triggered.connect(lambda: self.closeEvent())

        #file I/O actions
        save = QAction("&Save", self)
        load = QAction("&Load", self)
        # email = QAction("&Email", self)
        undo = QAction("&Undo", self)
        redo = QAction("&Redo", self)
        file_menu.addAction(save)
        file_menu.addAction(load)
        # file_menu.addAction(email)
        file_menu.addAction(undo)
        file_menu.addAction(redo)
        save.triggered.connect(lambda: self.saveFile())
        load.triggered.connect(lambda: self.loadFile())
        # email.triggered.connect(lambda: self.emailFile())
        undo.triggered.connect(lambda: self.undo())
        redo.triggered.connect(lambda: self.redo())

        #create simulation settings layout and running layout
        self.createSimulationSetting()
        self.createSimulationRunning()

        #right side toolbar to hold simulation settings
        setting = QToolBar()
        setting.addWidget(self.SimulationChoice)
        setting.addWidget(self.SimulationSetting)
        self.addToolBar(Qt.RightToolBarArea, setting)

        #display grid as central widget
        self.setCentralWidget(self.grid)

        #set fixed size for drag & drop precision
        self.setWindowTitle("Designer")
        self.changeStyle('fusion')


    def saveFile(self):
        path=QFileDialog.getSaveFileName(self, "Choose Directory","E:\\")
        #print(path[0] + ".qc")
        designer.giveGUIGrid(grid)
        designer.runSimulation()
        designer.saveSimulationToFile(path[0] + ".qc")

    def loadFile(self):
        dir_path=QFileDialog.getOpenFileName(self, "Choose .qc file","E:\\")
        print(dir_path[0])
        designer.loadSimulationFromFile(dir_path[0])
        updateGrid()
        designer.printDesign()

    def undo(self):
        f = tempfile.NamedTemporaryFile(delete=False)
        designer.saveSimulationToFile(f.name)
        redoStack.append(f.name)
        f.close()
        f = undoStack.pop()
        designer.loadSimulationFromFile(f)
        os.remove(f)
        updateGrid()
        designer.printDesign()

    def redo(self):
        f = tempfile.NamedTemporaryFile(delete=False)
        designer.saveSimulationToFile(f.name)
        undoStack.append(f.name)
        f.close()
        f = redoStack.pop()
        designer.loadSimulationFromFile(f)
        os.remove(f)
        updateGrid()
        designer.printDesign()


    #override close event to make sure pop-up window will close when
    #main window is close, otherwise a not-responding pop-up will remain
    #after main window is closed
    def closeEvent(self, event):          
        self.close()
        for f in undoStack:
            try:
                os.remove(f)
            except:
                pass
        for f in redoStack:
            try:
                os.remove(f)
            except:
                pass

    def changeStyle(self, styleName):
        QApplication.setStyle(QStyleFactory.create(styleName))
        self.changePalette()

    def changePalette(self):
        QApplication.setPalette(self.originalPalette)

    #create interface for running simulation
    def createSimulationRunning(self):
        self.SimulationChoice = QGroupBox("Simulation Actions")
        button1 = QPushButton()
        button1.setText("Run")
        button1.clicked.connect(runSimulation)
        button2 = QPushButton()
        button2.setText("Data Diagram")
        button2.clicked.connect(dataDiagramVisualization)
        button3 = QPushButton()
        button3.setText("LL(1) Grid Parser")
        button3.clicked.connect(showParseGrid)
        button4 = QPushButton()
        button4.setText("Tensor Network Diagram")
        button4.clicked.connect(showTensorNetwork)
        layout = QVBoxLayout()
        layout.addWidget(button1)
        layout.addWidget(button2)
        layout.addWidget(button4)
        layout.addWidget(button3)
        layout.addStretch(1)
        self.SimulationChoice.setLayout(layout)

    #a function that changes setting file and backend based on user's choice
    def updateSimulationTechnique(self, i):
        if("Q" in self.sim_box.currentText()):
            if self.external_sim_msg.msg_toggle:
                self.external_sim_msg.exec()
            changeSimulationTechniqueQiskit()

    #a function that allows user to set external backend warning msg off
    def externalMsgToggle(self, pushed):
        if (pushed.text() == "Ignore"):
            self.external_sim_msg.msg_toggle = False;

    #create interface for simulation settings
    def createSimulationSetting(self):
        self.SimulationSetting = QGroupBox("Simulation Setting")

        layout = QVBoxLayout()
        #check box for measurement, setting will be updated once toggled
        measurement = QCheckBox("Measurement")
        measurement.toggled.connect(self.TypeOnClicked)
        measurement.callsign = "measurement"
        layout.addWidget(measurement)

        #check box for gate suggestion, setting will be updated once toggled
        gate_suggestion = QCheckBox("Get Circuit Optimization")
        gate_suggestion.toggled.connect(self.TypeOnClicked)
        gate_suggestion.callsign = "suggestion"
        layout.addWidget(gate_suggestion)


        # Various other field boxes, obvious based on titling
        noice_label = QLabel("Noice Model")
        noice_selection = ["none", "other..."]
        noice_box = QComboBox()
        noice_box.addItems(noice_selection)
        layout.addWidget(noice_label)
        layout.addWidget(noice_box)

        optimization_label = QLabel("Optimization")
        optimization_selection = ["none", "other..."]
        optimization_box = QComboBox()
        optimization_box.addItems(optimization_selection)

        num_qubits = QSpinBox(self.SimulationSetting)
        num_qubits.setValue(5)
        num_qubits.callsign = "numqubit"
        qubit_label = QLabel("&Number of Qubits: ")
        qubit_label.setBuddy(num_qubits)
        num_qubits.valueChanged.connect(self.UpdateParameters)

        num_bits = QSpinBox(self.SimulationSetting)
        num_bits.setValue(5)
        num_bits.callsign = "numbit"
        bit_label = QLabel("&Number of bits: ")
        bit_label.setBuddy(num_bits)
        num_bits.valueChanged.connect(self.UpdateParameters)

        num_width = QSpinBox(self.SimulationSetting)
        num_width.setValue(8)
        num_width.callsign = "numwidth"
        width_label = QLabel("&Width: ")
        num_width.valueChanged.connect(self.UpdateParameters)

        #a message box that tells user external backend has been selected
        #'ignore' button has been overriden so that
        #click on it will let message never pop-up again
        self.external_sim_msg = QMessageBox()
        self.external_sim_msg.setIcon(QMessageBox.Information)
        self.external_sim_msg.setWindowTitle("External backend")
        self.external_sim_msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Ignore)
        #message on display
        self.external_sim_msg.setText("You have chosen an external backend. QCD will now run your circuit design on an external backend.")
        self.external_sim_msg.setInformativeText("Some external backend have different behaviors when accepting input. You can access their features via the menu bar. ")
        self.external_sim_msg.msg_toggle = True;
        self.external_sim_msg.buttonClicked.connect(self.externalMsgToggle)

        # Simulation selection panel
        Simulation = QLabel("Simulation Technique")
        sim_selection = ["Qiskit","MySim"]
        self.sim_box = QComboBox()
        self.sim_box.addItems(sim_selection)
        self.sim_box.currentIndexChanged.connect(self.updateSimulationTechnique)

        layout.addWidget(Simulation)
        layout.addWidget(self.sim_box)

        width_label.setBuddy(num_width)
        layout.addWidget(optimization_label)
        layout.addWidget(optimization_box)
        layout.addWidget(qubit_label)
        layout.addWidget(num_qubits)
        layout.addWidget(bit_label)
        layout.addWidget(num_bits)
        layout.addWidget(width_label)
        layout.addWidget(num_width)

        layout.addStretch(1)
        self.SimulationSetting.setLayout(layout)

    #integration function that connects checkboxs on gui to backend
    def TypeOnClicked(self):
        Button = self.sender()
        designer.settings.measurement = Button.isChecked()
        if (Button.callsign == "measurement"):
            changeMeasurement(Button.isChecked())
        elif (Button.callsign == "suggestion"):
            changeSuggestion(Button.isChecked())


    # Updates parameters locally and calls for forced change
    def UpdateParameters(self):
        spin = self.sender()
        val = spin.value()
        if (spin.callsign == "numqubit"):
            updateNumQubit(val)
            forceUpdate()
        elif (spin.callsign == "numbit"):
            updateNumBit(val)
            forceUpdate()
        elif (spin.callsign == "numwidth"):
            updateNumWidth(val)
            forceUpdate()

    def makeCustomGate(self):
        x1 = QtWidgets.QInputDialog.getInt(self, 'X1', 'Input:')
        if (x1[1] == True):
            print(x1[0])
            x2 = QtWidgets.QInputDialog.getInt(self, 'X2', 'Input:')
            if (x2[1] == True):
                print(x2[0])
                y1 = QtWidgets.QInputDialog.getInt(self, 'Y1', 'Input:')
                if (y1[1] == True):
                    print(y1[0])
                    y2 = QtWidgets.QInputDialog.getInt(self, 'Y2', 'Input:')
                    if (y2[1] == True):
                        print(y2[0])

        print(grid[y1[0]][x1[0] + offSetHorizontal])
        print(grid[y2[0]][x2[0] + offSetHorizontal])

        customGrid = [["-" for i in range(x2[0]-x1[0]+1)] for j in range(y2[0]-y1[0]+1)]

        xItr = 0
        yItr = 0
        for i in range(y1[0], y2[0] + 1):
            for j in range(x1[0], x2[0] + 1):
                customGrid[i-y1[0]][j-x1[0]] = grid[i][j+offSetHorizontal]

        customGateName = QtWidgets.QInputDialog.getText(self, 'Custom Gate Name', 'Input:')
        print(customGateName)
        if(customGateName[1] == False):
            return

        customGates[customGateName[0]] = customGrid

        forceUpdate()
        self.grid.updateGUILayout()
        print("--------------------------------------")
        for i in range(len(grid)):
            strtemp = ""
            for j in range(len(grid[0])):
                strtemp += grid[i][j]
            print(strtemp)
        print("--------------------------------------")

        
class PartialSimulationTab(QDialog):
    def __init__(self, parent=Window):
        super(PartialSimulationTab, self).__init__()
        self.layout = QVBoxLayout(self)

        # basic initialization
        self.setWindowTitle("Tensor Network Simulation Settings")
        self.tabs = QTabWidget()
        self.tab_addvar = QWidget()
        self.tab_addobj = QWidget()
        self.submit_but = QPushButton()
        self.submit_but.setText("Submit")
        self.submit_but.clicked.connect(lambda: self.submit())

        self.tabs.addTab(self.tab_addvar, "Enter Sample Bitstrings")
        self.tabs.addTab(self.tab_addobj, "Approximation Settings")

        self.tab_addvar.layout = QVBoxLayout(self)
        self.dwave_var = QTextEdit()
        self.dwave_var.setPlaceholderText("Add your bitstrings here seperated by a newline")
        self.tab_addvar.layout.addWidget(self.dwave_var)
        self.tab_addvar.setLayout(self.tab_addvar.layout)

        self.tab_addobj.layout = QVBoxLayout(self)
        #self.tab_addobj.layout.addWidget(self.dwave_obj)
        self.gateCheckBox = QCheckBox("Gate Split Reduce (only if large tensors)")
        self.tab_addobj.layout.addWidget(self.gateCheckBox)
        self.gateCheckBox.setChecked(False)
        self.gateCheckBox.stateChanged.connect(lambda: self.click(self.gateCheckBox))
        self.lineSVDCutoff = QLineEdit(self)
        self.lineSVDCutoff.setPlaceholderText("SVD Cutoff Absolute")
        self.tab_addobj.layout.addWidget(self.lineSVDCutoff)
        self.lineSVDCutoffTrunc = QLineEdit(self)
        self.lineSVDCutoffTrunc.setPlaceholderText("SVD Cutoff Truncation")
        self.tab_addobj.layout.addWidget(self.lineSVDCutoffTrunc)
        self.tab_addobj.setLayout(self.tab_addobj.layout)

        self.layout.addWidget(self.tabs)
        self.layout.addWidget(self.submit_but)
        self.setLayout(self.layout)
        self.resize(800, 600)

    # override close event to update the text we got from user when tab is closed
    def closeEvent(self, event):
        global cuQuantumBitStrings
        global cuQuantumConfig
        cuQuantumBitStrings = self.dwave_var.toPlainText()
        if(len(self.lineSVDCutoff.text()) > 0):
            cuQuantumConfig[0] = float(self.lineSVDCutoff.text())
        if(len(self.lineSVDCutoffTrunc.text()) > 0):
            cuQuantumConfig[1] = float(self.lineSVDCutoffTrunc.text())
        self.close()

    def submit(self):
        global cuQuantumBitStrings
        global cuQuantumConfig
        cuQuantumBitStrings = self.dwave_var.toPlainText()
        if(len(self.lineSVDCutoff.text()) > 0):
            cuQuantumConfig[0] = float(self.lineSVDCutoff.text())
        if(len(self.lineSVDCutoffTrunc.text()) > 0):
            cuQuantumConfig[1] = float(self.lineSVDCutoffTrunc.text())
        self.close()
        
    def click(self, checkBox):
        global cuQuantumGateSplit
        if(checkBox.isChecked()):
            cuQuantumGateSplit = 1
        else:
            cuQuantumGateSplit = 0
        
# Create the application, window, and close application if asked
app = QApplication(sys.argv)
cuQuantumTab = PartialSimulationTab()
window = Window()
window.show()
sys.exit(app.exec_())