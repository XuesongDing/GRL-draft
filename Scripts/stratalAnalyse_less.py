##~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~##
##                                                                                   ##
##  This file forms part of the Badlands surface processes modelling companion.      ##
##                                                                                   ##
##  For full license and copyright information, please refer to the LICENSE.md file  ##
##  located at the project root, or contact the authors.                             ##
##                                                                                   ##
##~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~##
"""
Here we set usefull functions used to analyse stratigraphic sequences from Badlands outputs.
"""

import os
import math
import h5py
import errno
import numpy as np
import pandas as pd
from cmocean import cm
import colorlover as cl
from scipy import interpolate
import matplotlib.pyplot as plt
from scipy.spatial import cKDTree
import xml.etree.ElementTree as ETO
import scipy.ndimage.filters as filters
from scipy.interpolate import RectBivariateSpline
from scipy.ndimage.filters import gaussian_filter

import plotly
from plotly import tools
from plotly.graph_objs import *
plotly.offline.init_notebook_mode()

import warnings
warnings.simplefilter(action = "ignore", category = FutureWarning)

def readSea(seafile):
    """
    Plot sea level curve.
    Parameters
    ----------
    variable: seafile
        Absolute path of the sea-lelve data.
    """

    df=pd.read_csv(seafile, sep=r'\s+',header=None)
    SLtime,sealevel = df[0],df[1]

    return SLtime,sealevel

def viewData(x0 = None, y0 = None, width = 800, height = 400, linesize = 3, color = '#6666FF',
             xlegend = 'xaxis', ylegend = 'yaxis', title = 'view data'):
    """
    Plot multiple data on a graph.
    Parameters
    ----------
    variable: x0, y0
        Data for plot
    variable: width, height
        Figure width and height.
    variable: linesize
        Requested size for the line.
    variable: color
        
    variable: xlegend
        Legend of the x axis.
    variable: ylegend
        Legend of the y axis.
    variable: title
        Title of the graph.
    """
    trace = Scatter(
        x=x0,
        y=y0,
        mode='lines',
        line=dict(
            shape='line',
            color = color,
            width = linesize
        ),
        fill=None
    )

    layout = dict(
            title=title,
            font=dict(size=10),
            width=width,
            height=height,
            showlegend = False,
            xaxis=dict(title=xlegend,
                       ticks='outside',
                       zeroline=False,
                       showline=True,
                       mirror='ticks'),
            yaxis=dict(title=ylegend,
                       ticks='outside',
                       zeroline=False,
                       showline=True,
                       mirror='ticks')
            )

    fig = Figure(data=[trace], layout=layout)
    plotly.offline.iplot(fig)

    return

def depthID(cs = None, sealevel = None, envIDs = None):
    """
    Calculate the position of different depositional environments for Wheeler diagram.
    Parameters
    ----------
    variable: sealevel
        The value of sea level through time.
    variable: envIDs
        Range of water depth of each depostional environment.
    """
    envID = np.zeros(len(envIDs))
    for i in range(len(envIDs)):
        envID[i] = np.amax(np.where((cs.secDep[cs.nz-1]) > (sealevel - envIDs[i]))[0])

    return envID

class stratalSection:
    """
    Class for creating stratigraphic cross-sections from Badlands outputs.
    """

    def __init__(self, folder=None, ncpus=1):
        """
        Initialization function which takes the folder path to Badlands outputs
        and the number of CPUs used to run the simulation.

        Parameters
        ----------
        variable : folder
            Folder path to Badlands outputs.
        variable: ncpus
            Number of CPUs used to run the simulation.
        """

        self.folder = folder
        if not os.path.isdir(folder):
            raise RuntimeError('The given folder cannot be found or the path is incomplete.')

        self.ncpus = ncpus
        if ncpus > 1:
            raise RuntimeError('Multi-processors function not implemented yet!')

        self.x = None
        self.y = None
        self.xi = None
        self.yi = None
        self.dx = None
        self.dist = None
        self.dx = None
        self.nx = None
        self.ny = None
        self.nz = None
        self.dep = None
        self.th = None
        #self.elev = None
        self.xsec = None
        self.ysec = None
        self.secTh = []
        self.secDep = []
        #self.secElev = []

        self.shoreID = None
        self.accom_shore = None
        self.sed_shore = None
        self.depoend = None

        return

    def _buildShoreline(self, cs = None, cs_b = None, sealevel = None, sealevel_b = None):

        shoreID = np.amax(np.where(cs.secDep[cs.nz-1]>=sealevel)[0])
        shoreID_b = np.amax(np.where(cs_b.secDep[cs_b.nz-1]>=sealevel_b)[0])
        accom = sealevel - cs.secDep[cs_b.nz-1][shoreID_b]
        sed = cs.secDep[cs.nz-1][shoreID_b] - cs.secDep[cs_b.nz-1][shoreID_b]
        depoend = np.amax(np.where(cs.secTh[cs.nz-1][shoreID:len(cs.secTh[0])]>0.001)[0]) + shoreID

        return shoreID, accom, sed, depoend

    def buildParameters(self, npts, strat_all, sealevel):

        # Calculate cross-section parameters
        shoreID = np.zeros(npts)
        accom_shore = np.zeros(npts)
        sed_shore = np.zeros(npts)
        depoend = np.zeros(npts)

        shoreID[0], accom_shore[0], sed_shore[0], depoend[0] = self._buildShoreline(cs = strat_all[0],
                                            cs_b = strat_all[0], sealevel = sealevel[0], sealevel_b = sealevel[0])

        for i in range(1,npts):
            shoreID[i], accom_shore[i], sed_shore[i], depoend[i],  = self._buildShoreline(cs = strat_all[i], cs_b = strat_all[i-1], sealevel = sealevel[i], sealevel_b = sealevel[i-1])

        self.shoreID = shoreID
        self.accom_shore = accom_shore
        self.sed_shore = sed_shore
        self.depoend = depoend

        return

    def loadStratigraphy(self, timestep=0):
        """
        Read the HDF5 file for a given time step.
        Parameters
        ----------
        variable : timestep
            Time step to load.
        """

        for i in range(0, self.ncpus):
            df = h5py.File('%s/sed.time%s.p%s.hdf5'%(self.folder, timestep, i), 'r')
            #print(list(df.keys()))
            coords = np.array((df['/coords']))
            #coords = np.round(coords,9)
            layDepth = np.array((df['/layDepth']))
            #layElev = np.array((df['/layElev']))
            layThick = np.array((df['/layThick']))
            if i == 0:
                x, y = np.hsplit(coords, 2)
                dep = layDepth
                #elev = layElev
                th = layThick

        self.dx = x[1]-x[0]
        self.x = x
        self.y = y
        self.nx = int((x.max() - x.min())/self.dx+1)
        self.ny = int((y.max() - y.min())/self.dx+1)
        self.nz = dep.shape[1]
        self.xi = np.linspace(x.min(), x.max(), self.nx)
        self.yi = np.linspace(y.min(), y.max(), self.ny)
        self.dep = dep.reshape((self.ny,self.nx,self.nz))
        #self.elev = elev.reshape((self.ny,self.nx,self.nz))
        self.th = th.reshape((self.ny,self.nx,self.nz))

        return

    def _cross_section(self, xo, yo, xm, ym, pts):
        """
        Compute cross section coordinates.
        """

        if xm == xo:
            ysec = np.linspace(yo, ym, pts)
            xsec = np.zeros(pts)
            xsec.fill(xo)
        elif ym == yo:
            xsec = np.linspace(xo, xm, pts)
            ysec = np.zeros(pts)
            ysec.fill(yo)
        else:
            a = (ym-yo)/(xm-xo)
            b = yo - a * xo
            xsec = np.linspace(xo, xm, pts)
            ysec = a * xsec + b

        return xsec, ysec

    def buildSection(self, xo = None, yo = None, xm = None, ym = None,
                    pts = 100, gfilter = 5):
        """
        Extract a slice from the 3D data set and compute the stratigraphic layers.
        Parameters
        ----------
        variable: xo, yo
            Lower X,Y coordinates of the cross-section.
        variable: xm, ym
            Upper X,Y coordinates of the cross-section.
        variable: pts
            Number of points to discretise the cross-section.
        variable: gfilter
            Gaussian smoothing filter.
        """

        if xm > self.x.max():
            xm = self.x.max()

        if ym > self.y.max():
            ym = self.y.max()

        if xo < self.x.min():
            xo = self.x.min()

        if yo < self.y.min():
            yo = self.y.min()

        xsec, ysec = self._cross_section(xo, yo, xm, ym, pts)
        self.dist = np.sqrt(( xsec - xo )**2 + ( ysec - yo )**2)
        self.xsec = xsec
        self.ysec = ysec
        for k in range(self.nz):
            # Thick
            rect_B_spline = RectBivariateSpline(self.yi, self.xi, self.th[:,:,k])
            data = rect_B_spline.ev(ysec, xsec)
            secTh = filters.gaussian_filter1d(data,sigma=gfilter)
            secTh[secTh < 0] = 0
            self.secTh.append(secTh)

            # Elev
            #rect_B_spline1 = RectBivariateSpline(self.yi, self.xi, self.elev[:,:,k])
            #data1 = rect_B_spline1.ev(ysec, xsec)
            #secElev = filters.gaussian_filter1d(data1,sigma=gfilter)
            #self.secElev.append(secElev)

            # Depth
            rect_B_spline2 = RectBivariateSpline(self.yi, self.xi, self.dep[:,:,k])
            data2 = rect_B_spline2.ev(ysec, xsec)
            secDep = filters.gaussian_filter1d(data2,sigma=gfilter)
            self.secDep.append(secDep)

        # Ensure the spline interpolation does not create underlying layers above upper ones
        topsec = self.secDep[self.nz-1]
        for k in range(self.nz-2,-1,-1):
            secDep = self.secDep[k]
            self.secDep[k] = np.minimum(secDep, topsec)
            topsec = self.secDep[k]

        return
