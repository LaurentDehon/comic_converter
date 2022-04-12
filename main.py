from PyQt5.QtWidgets import QApplication, QMainWindow, QDesktopWidget, QSlider, QRadioButton, QLabel, QWidget, QVBoxLayout, QMessageBox, QGridLayout
from PyQt5.QtWidgets import QPushButton, QListWidget, QSizePolicy, QProgressBar, QFileDialog, QListWidgetItem, QShortcut, QAction
from PyQt5.QtGui import QFont, QKeySequence, QIcon
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QRunnable, QThreadPool, Qt
from PIL import Image
import sys
import os
from os.path import splitext
import shutil
import fitz
import configparser


class WorkerSignals(QObject):

	startDoc = pyqtSignal(str, int)
	finishedDoc = pyqtSignal()
	finishedTask = pyqtSignal()
	progress = pyqtSignal(int)


class Worker(QRunnable):

	def __init__(self, names):

		super(Worker, self).__init__()
		self.signals = WorkerSignals()
		self.names = names

	@pyqtSlot()
	def run(self):

		config = configparser.ConfigParser()
		config.read('config.ini')
		quality = config['default']['quality']
		extension = config['default']['format']

		for name in self.names:
			pdffile = name
			doc = fitz.open(pdffile)
			self.signals.startDoc.emit(name, doc.pageCount)
			os.mkdir(name[:-4])
			for i in range(0, doc.pageCount):
				page = doc.loadPage(i)
				if quality == 'low':
					zoom = 0.5
				elif quality == 'medium':
					zoom = 1
				else:
					zoom = 2
				mat = fitz.Matrix(zoom, zoom)
				pix = page.getPixmap(mat)
				pix.writePNG('{}\\{:002d}.jpg'.format(name[:-4], i))
				im = Image.open('{}\\{:002d}.jpg'.format(name[:-4], i))
				rgb_im = im.convert('RGB')
				rgb_im.save('{}\\{:002d}.jpg'.format(name[:-4], i))
				self.signals.progress.emit(i)

			shutil.make_archive(name[:-4], "zip", name[:-4])
			os.rename(name[:-4] + '.zip', name[:-4] + '.{}'.format(extension))
			shutil.rmtree(name[:-4], ignore_errors=True)
			self.signals.finishedDoc.emit()

		self.signals.finishedTask.emit()


class ListSignal(QObject):

	dropped = pyqtSignal(list)
	emptyList = pyqtSignal()


class ListOfFiles(QListWidget):

	def __init__(self, type, parent=None):

		super(ListOfFiles, self).__init__(parent)
		self.signals = ListSignal()
		self.setAcceptDrops(True)
		self.delItem = QShortcut(QKeySequence(Qt.Key_Delete), self)
		self.delItem.activated.connect(self.delete_item)
		self.setSelectionMode(3)

	def dragEnterEvent(self, event):

		if event.mimeData().hasUrls:
			event.accept()
		else:
			event.ignore()

	def dragMoveEvent(self, event):

		if event.mimeData().hasUrls:
			event.setDropAction(Qt.CopyAction)
			event.accept()
		else:
			event.ignore()

	def dropEvent(self, event):

		if event.mimeData().hasUrls:
			event.setDropAction(Qt.CopyAction)
			event.accept()
			files = []
			for url in event.mimeData().urls():
				files.append(str(url.toLocalFile()))

			self.signals.dropped.emit(files)
		else:
			event.ignore()

	def delete_item(self):
		list_items = self.selectedItems()
		for item in list_items:
			self.takeItem(self.row(item))
			if self.count() == 0:
				self.signals.emptyList.emit()


class Settings(QWidget):

	def __init__(self):

		super(Settings, self).__init__()
		self.screen = QDesktopWidget().screenGeometry(0)
		self.setGeometry(int((self.screen.width()-250)/2), int((self.screen.height()-100)/2), 250, 100)
		self.setFixedSize(250, 100)
		self.setWindowTitle("Settings")
		self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
		self.init_ui()

	def init_ui(self):

		winIcon = QIcon('Settings.ico')
		self.setWindowIcon(winIcon)

		self.config = configparser.ConfigParser()
		self.config.read('config.ini')
		self.quality = self.config['default']['quality']
		self.extension = self.config['default']['format']

		self.widget = QWidget()

		self.lblQuality = QLabel('Quality', self)
		self.lblQuality.setGeometry(10, 20, 100, 20)

		self.sldQuality = QSlider(Qt.Horizontal, self)
		self.sldQuality.setGeometry(80, 20, 150, 20)
		self.sldQuality.setMinimum(0)
		self.sldQuality.setMaximum(2)
		self.sldQuality.setTickPosition(3)
		if self.quality == 'low':
			self.sldQuality.setValue(0)
		elif self.quality == 'medium':
			self.sldQuality.setValue(1)
		else:
			self.sldQuality.setValue(2)

		self.sldQuality.valueChanged.connect(self.update_slider)

		self.lblExtension = QLabel('Format', self)
		self.lblExtension.setGeometry(10, 50, 100, 20)
		self.rdoCBZ = QRadioButton('CBZ', self)
		self.rdoCBZ.setGeometry(80, 50, 100, 20)
		self.rdoCBZ.toggled.connect(self.select_cbz)
		self.rdoCBR = QRadioButton('CBR', self)
		self.rdoCBR.setGeometry(140, 50, 100, 20)
		self.rdoCBR.toggled.connect(self.select_cbr)
		if self.extension == 'cbz':
			self.rdoCBZ.setChecked(True)
		else:
			self.rdoCBR.setChecked(True)

	def update_slider(self):

		if self.sldQuality.value() == 0:
			self.quality = 'low'
		elif self.sldQuality.value() == 1:
			self.quality = 'medium'
		else:
			self.quality = 'high'

		self.config['default']['quality'] = self.quality
		with open('config.ini', 'w') as configfile:
			self.config.write(configfile)

	def select_cbz(self):

		self.config['default']['format'] = 'cbz'
		with open('config.ini', 'w') as configfile:
			self.config.write(configfile)

	def select_cbr(self):

		self.config['default']['format'] = 'cbr'
		with open('config.ini', 'w') as configfile:
			self.config.write(configfile)


class Converter(QMainWindow):

	def __init__(self):

		super(Converter, self).__init__()
		self.threadpool = QThreadPool()
		self.screen = QDesktopWidget().screenGeometry(0)
		self.setGeometry(int((self.screen.width()-700)/2), int((self.screen.height()-500)/2), 700, 500)
		self.setWindowTitle("Joker 1.0")
		self.statusBar().showMessage("")
		self.settings = None
		self.listOfFiles = ListOfFiles(self)
		self.listOfFiles.signals.dropped.connect(self.files_dropped)
		self.listOfFiles.signals.emptyList.connect(self.disable_convert)
		self.init_ui()

	def init_ui(self):

		winIcon = QIcon('Joker.ico')
		self.setWindowIcon(winIcon)

		bar = self.menuBar()
		fileMenu = bar.addMenu('&File')
		actionSettings = QAction(QIcon('Settings.ico'), 'Settings', self)
		actionExit = QAction(QIcon('Exit.ico'), 'Exit', self)
		fileMenu.addAction(actionSettings)
		fileMenu.addAction(actionExit)
		actionSettings.triggered.connect(self.show_settings)
		actionExit.triggered.connect(self.closeEvent)

		self.widget = QWidget()
		self.vbox = QVBoxLayout()

		self.btnSelect = QPushButton("Select PDF(s)", self)
		self.btnSelect.setMaximumHeight(50)
		self.btnSelect.setFont(QFont("Calibri", 20))
		self.btnSelect.clicked.connect(self.select_pdf)
		self.btnSelect.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
		self.vbox.addWidget(self.btnSelect)

		self.vbox.addWidget(self.listOfFiles)

		self.progress = QProgressBar()
		self.vbox.addWidget(self.progress)

		self.btnConvert = QPushButton("Convert", self)
		self.btnConvert.setMaximumHeight(50)
		self.btnConvert.setFont(QFont("Calibri", 20))
		self.btnConvert.clicked.connect(self.convert_pdf)
		self.btnConvert.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
		self.btnConvert.setEnabled(False)
		self.vbox.addWidget(self.btnConvert)

		self.widget.setLayout(self.vbox)
		self.setCentralWidget(self.widget)
		self.show()

	def closeEvent(self, event):

		app.closeAllWindows()
		app.quit()

	def show_settings(self):

		if self.settings is None:
			self.settings = Settings()

		self.settings.show()

	def select_pdf(self):

		filter = "PDF (*.pdf)"
		filenames = QFileDialog()
		filenames.setFileMode(QFileDialog.ExistingFiles)
		self.names, _ = filenames.getOpenFileNames(self, "Open files", "D:\\", filter)
		for index, name in enumerate(self.names):
			found = self.listOfFiles.findItems(name, Qt.MatchExactly)
			if len(found) == 0 and name[-4:] == ".pdf":
				item = QListWidgetItem(name, self.listOfFiles)
				item.setToolTip("Press 'DEL' key to delete")

		if self.listOfFiles.count() > 0:
			self.btnConvert.setEnabled(True)

	def files_dropped(self, names):

		self.names = names
		for index, name in enumerate(self.names):
			found = self.listOfFiles.findItems(name, Qt.MatchExactly)
			if len(found) == 0 and name[-4:] == ".pdf":
				item = QListWidgetItem(name, self.listOfFiles)
				item.setToolTip("Press 'DEL' key to delete")

		if self.listOfFiles.count() > 0:
			self.btnConvert.setEnabled(True)

	def convert_pdf(self):

		items = []
		for i in range(0, self.listOfFiles.count()):
			items.append(self.listOfFiles.item(i).text())

		worker = Worker(items)
		self.threadpool.start(worker)
		worker.signals.startDoc.connect(self.start_conversion)
		worker.signals.finishedDoc.connect(self.remove_from_list)
		worker.signals.finishedTask.connect(self.end_conversion)
		worker.signals.progress.connect(self.update_progress)

	def remove_from_list(self):

		self.listOfFiles.takeItem(0)

	def start_conversion(self, name, i):

		self.statusBar().showMessage("Converting {}...".format(name))
		self.progress.setMaximum(i)
		self.btnConvert.setEnabled(False)

	def end_conversion(self):

		self.progress.setValue(0)
		self.statusBar().showMessage("Done")

	def update_progress(self, i):

		self.progress.setValue(i + 1)

	def disable_convert(self):

		self.btnConvert.setEnabled(False)


if __name__ == '__main__':
	app = QApplication(sys.argv)
	app.setStyle("Fusion")
	main = Converter()
	sys.exit(app.exec_())
