# vim: set expandtab shiftwidth=2 softtabstop=2:

# ToolUI classes may also override
#   "delete" - called to clean up before instance is deleted
#
# Seems like Tool exists inside the bundle and needs overridding

from chimerax.core.tools import ToolInstance
from chimerax.core.models import Models
from chimerax.core.map.volume import Volume
from chimerax.core.atomic.structure import AtomicStructure
from chimerax.core.commands import select

import matplotlib
matplotlib.use("Qt5Agg", force=True)

from matplotlib.backends.backend_qt5agg import FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

import os, math 
from . import tool_layout

class ToolUI(ToolInstance):

  def __init__(self, session, tool_name):
    ''' Call the special layout function '''
    ToolInstance.__init__(self, session, tool_name)
    tool_layout.layout_main(self)

  def _select_model_map(self):
    ''' Our way of selecting the model and map for scoring.
    We take the first model we find and the first map we 
    find that are selected. Probably needs improvement.'''

    atomic_model = None
    map_model = None

    for mm in self.session.selection.models():
      if isinstance(mm, AtomicStructure):
        atomic_model = mm
        break
    
    for mm in self.session.selection.models():
      if isinstance(mm, Volume):
        map_model = mm
        break
 
    if atomic_model == None or map_model == None:
      print("TEMPY Error: Please select one model and one map.")
      return (False, None, None)
    
    return (True, atomic_model, map_model)

  def _select_models_map(self):
    ''' Our way of selecting the models and map for scoring with smoc.
    We take the first model we find and the first map we 
    find that are selected. Probably needs improvement.'''

    atomic_models = []
    map_model = None
    
    for mm in self.session.selection.models():
      if isinstance(mm, AtomicStructure):
          atomic_models.append(mm)
    
    for mm in self.session.selection.models():
      if isinstance(mm, Volume):
          map_model = mm
          break
 
    if len(atomic_models) == 0 or map_model == None:
      print("TEMPY Error: Please select one or more models and one map.")
      return (False, None, None)
    
    return (True, atomic_models, map_model)

  def _select_two(self):
    ''' Take the first two things selected. We will see what they are used
    for later. Used in the NMI scoring.'''

    if len(self.session.selection.models()) == 2:
      return (True, self.session.selection.models()[0], self.session.selection.models()[1])
  
    print("TEMPY Error: Please select two and only two maps/models.")
    return(False,None,None)

  def _sccc_score(self):
    ''' Run the sccc score as a graphical function, 
    setting the colours of the chosen model.'''

    from .sccc import score

    # Check rigid score file
    rb_file = self._widget_rigid_file_sccc.text()
    if not os.path.isfile(rb_file):
      print("TEMPY error: File " + rb_file + " does not exist")
      return

    try:
      sim_sigma = float(self._widget_sigma_sccc.text())
      rez = float(self._widget_rez_sccc.text())
    except:
      print("TEMPY Error: Check the values for rez and sigma")
      return

    # Find models
    result, atomic_model, map_model = self._select_model_map()
    if result:
      score(self.session, atomic_model, map_model, rb_file, rez, sim_sigma)

  def _smoc_score(self):
    ''' Compute the smoc score but also plot
    the scores below the tool.'''

    from .smoc import score
    from PyQt5.QtWidgets import QVBoxLayout

    # Check Rigid file
    # Optional with smoc
    rb_file = self._widget_rigid_file_smoc.text()
    if not os.path.isfile(rb_file):
      rb_file =""

    # Check model and map
    result, atomic_models, map_model = self._select_models_map()    
    if not result:
      return
  
    # Check the options
    try:
      sim_sigma = float(self._widget_sigma_smoc.text())
      rez = float(self._widget_rez_smoc.text())
      win = int(float(self._widget_window_smoc.text()))
    except:
      print("TEMPY Error: Check the values for rez, sigma and window.")
      return
 
    # a figure instance to plot on
    if self._figure == None:
      self._figure = matplotlib.figure.Figure()

    # TODO - This adds a lot more layers if we keep scoring. A good idea to show improvement
    # perhaps but we may need a way to remove graphs. For now, lets just go with replacement. 
    if self._canvas == None:
      self._canvas = FigureCanvas(self._figure)
      
      parent = self.tool_window.ui_area
      toolbar = NavigationToolbar(self._canvas, parent)
     
      sublayout = QVBoxLayout()
      sublayout.addWidget(toolbar)
      sublayout.addWidget(self._canvas)
    
      self.top_layout.addLayout(sublayout)
      self._subplot = self._figure.add_subplot(111)
      self._figure.xlabel = 'Residue_num'
      self._figure.ylabel = 'SMOC'
      self._canvas.mpl_connect('button_press_event', self.onclick)

    self._subplot.cla()
    self._figure.subplots_adjust(bottom=0.25)
   
    # Call score
    idx = 0
    self._current_smoc_scores = [] # keep for graph clicking
    self._scored_models = atomic_models
    
    for (dict_chains_scores, dict_reslist) in score(self.session, atomic_models,
        map_model, rb_file, rez, sim_sigma, win):

      self._current_smoc_scores.append([])

      # TODO - we are mixing chains here. Need to check that sort of thing really
      for ch in dict_chains_scores:
        reslist = []
        scorelist = []
        
        for res in dict_reslist[ch]:
          reslist.append(res)
          tp = dict_chains_scores[ch][res] 
          scorelist.append(tp)
          self._current_smoc_scores[idx].append(tp)

        col = atomic_models[idx].single_color
        col = (float(col[0])/256.0,float(col[1])/256.0,float(col[2])/256.0)
        self._subplot.plot(reslist,scorelist,linewidth=1.0,label="smoc score", color=col)
      
      idx+=1

    # refresh canvas
    self._canvas.draw()

  def onclick(self, event):
    ''' This is called when we click on the graph. We check to see which residue we are closest to by rounding down. '''

    if event.x != None and event.y != None and event.xdata != None and event.ydata != None:
      #print('%s click: button=%d, x=%d, y=%d, xdata=%f, ydata=%f' % ('double' if event.dblclick else 'single', event.button, event.x, event.y, event.xdata, event.ydata))
      res = int(math.floor(event.xdata))
       # Now find which line we are nearest
      sc = event.ydata 
      tc = math.fabs(float(self._current_smoc_scores[0][res][0]) - event.ydata)
      smodel = 0
      idx = 0

      for mm in self._current_smoc_scores:
        tb = math.fabs(float(mm[res][0]) - event.ydata) 
        if tb < tc:
          tc = tb
          smodel = idx
        idx += 1

      print("Clicked residue " + str(res) + " on model " + self._scored_models[smodel].__str__())
      # clear selection and reselect
      self.session.selection.clear()
      sres = self._scored_models[smodel].residues[res]
      
      for atom in sres.atoms:
        atom.selected = True
      # TODO - do we want bonds as well or are they already selected?

  def _nmi_score(self):
    ''' Run the nmi score, printing to the log'''
    from .nmi import score

    try:
      rez1 = float(self._widget_rez_nmi.text())
      rez2 = float(self._widget_rez2_nmi.text())
      contour1 = float(self._widget_c1_nmi.text())
      contour2 = float(self._widget_c2_nmi.text()) 
    except:
      print("TEMPY Error: Check the values for rez1, rez2, c1 and c2")
      return

    # Find models
    result, scoringMapModel1, scoringMapModel2 = self._select_two()
    nmi_score = 0.0
    if result:
      if isinstance(scoringMapModel1, Volume) and isinstance(scoringMapModel2, AtomicStructure):
        nmi_score = score(self.session, scoringMapModel2, scoringMapModel1, None, None, rez1, rez2, contour1, contour2 )
      
      elif isinstance(scoringMapModel2, Volume) and isinstance(scoringMapModel1, AtomicStructure):
        nmi_score = score(self.session, scoringMapModel1, scoringMapModel2, None, None, rez1, rez2, contour1, contour2 )
      
      elif isinstance(scoringMapModel1, Volume) and isinstance(scoringMapModel2, Volume):
        nmi_score = score(self.session, None, scoringMapModel1, None, scoringMapModel2, rez1, rez2, contour1, contour2 )
      else :
        print("TEMPY Error: Please provide a map and model, or two maps.")
        return
        
      print("NMI Score: ", nmi_score)

  def _select_rigid_file_sccc(self):
    from PyQt5.QtWidgets import QFileDialog
    filename = QFileDialog.getOpenFileName(None, 'OpenFile')
    print(filename)
    self._widget_rigid_file_sccc.setText(filename[0])

  def _select_rigid_file_smoc(self):
    from PyQt5.QtWidgets import QFileDialog
    filename = QFileDialog.getOpenFileName(None, 'OpenFile')
    print(filename)
    self._widget_rigid_file_smoc.setText(filename[0])


  def _html_view(self):
    print("HTML Test")

  def delete(self):
    #t = self.session.triggers
    #t.remove_handler(self._add_handler)
    #t.remove_handler(self._remove_handler)
    super().delete()

  def take_snapshot(self, session, flags):
    # For now, do not save anything in session.
    # Need to figure out which attributes (like UI widgets)
    # should start with _ so that they are not saved in sessions.
    # And add addition data to superclass data.
    return super().take_snapshot(session, flags)

  @classmethod
  def restore_snapshot(cls, session, data):
    # For now do nothing.  Should unpack data and restart tool.
    return None
