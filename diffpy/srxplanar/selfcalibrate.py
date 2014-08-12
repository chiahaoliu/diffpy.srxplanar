import numpy as np
import scipy as sp
import os
from functools import partial
from scipy.optimize import minimize, leastsq, fmin_bfgs, fmin_l_bfgs_b, fmin_tnc, minimize_scalar, fmin_powell

def halfcut(p, srx, image, xycenter, qind=[50, 1000], show=False, mode='x', output=0):
    '''
    cut the image into two half, integrate them and compare the results, if the calibration 
    information is correct, two half should give same results.
    
    :param p: calibration parameters
    :param srx: SrXplanar object, object to do the integration
    :param image: str or 2d array, image to be calibrated
    :param xycenter: [int, int], cut position
    :param qind: [int, int], range of q to calculate the difference
    :param show: bool, True to plot the cut
    :param mode: str, mode of calibration, could be x, y, tilt, rotation, all
    :param output: int, 0 to return one number (sum of square of difference),
        1 to return the difference array
    
    :return: sum of square of difference or difference array
    '''
    if mode == 'x':
        srx.updateConfig(xbeamcenter=p)
    elif mode == 'y':
        srx.updateConfig(ybeamcenter=p)
    elif mode == 'tilt':
        srx.updateConfig(tiltd=p)
    elif mode == 'rotation':
        srx.updateConfig(rotationd=p)
    elif mode == 'all':
        srx.updateConfig(xbeamcenter=p[0],
                         ybeamcenter=p[1],
                         rotationd=p[2],
                         tiltd=p[3])
    elif mode == 'xy':
        srx.updateConfig(xbeamcenter=p[0],
                         ybeamcenter=p[1])
        
    kwargs = {'savename':None,
              'savefile':False,
              'flip':False,
              'correction':False,
              }
    if mode != 'y':
        # x half
        mask = np.zeros((srx.config.ydimension, srx.config.xdimension), dtype=bool)
        mask[:, :xycenter[0]] = 1
        res1 = srx.integrate(image, extramask=mask, **kwargs)
        chi1 = res1['chi'][1][qind[0]:qind[1]]
    
        mask = np.logical_not(mask)
        res2 = srx.integrate(image, extramask=mask, **kwargs)
        chi2 = res2['chi'][1][qind[0]:qind[1]]
        
    if mode != 'x':
        # y half
        mask = np.zeros((srx.config.ydimension, srx.config.xdimension), dtype=bool)
        mask[:xycenter[1], :] = 1
        res3 = srx.integrate(image, extramask=mask, **kwargs)
        chi3 = res3['chi'][1][qind[0]:qind[1]]
    
        mask = np.logical_not(mask)
        res4 = srx.integrate(image, extramask=mask, **kwargs)
        chi4 = res4['chi'][1][qind[0]:qind[1]]
        
    if mode == 'x':
        rv = chi1 - chi2
        rv = rv / rv.max()
    elif mode == 'y':
        rv = chi3 - chi4
        rv = rv / rv.max()
    else:
        r1 = chi1 - chi2
        r2 = chi3 - chi4
        # r3 = chi1 - chi3
        # r4 = chi2 - chi4
        # rv = np.concatenate([r1 / r1.max(), r2 / r2.max(), r3 / r3.max(), r4 / r4.max()])
        rv = np.concatenate([r1 / r1.mean(), r2 / r2.mean()])
    
    rv0 = np.sum(rv ** 2)
    print p
    print rv0
    if output == 0:
       rv = rv0

    if show:
        print p
        print rv
        import matplotlib.pyplot as plt
        plt.figure(1)
        plt.clf()
        if mode != 'y':
            plt.plot(res1['chi'][0], res1['chi'][1])
            plt.plot(res2['chi'][0], res2['chi'][1])
        if mode != 'x':
            plt.plot(res3['chi'][0], res3['chi'][1])
            plt.plot(res4['chi'][0], res4['chi'][1])
        plt.show()
    return rv


def selfCalibrateX(srx, image, qmax=20.0, mode='all', output=0):
    '''
    Do the self calibration using mode X
    
    the initial value is read from the current value of srx object, and the 
    refined results will be writrn into the srx object
    
    :param srx: SrXplanar object, object to do the integration
    :param image: str or 2d array, image to be calibrated
    :param qmax: float, max of q value used in difference calculation
    :param mode: str, mode of calibration, could be x, y, tilt, rotation, all
    :param output: int, 0 to use fmin optimizer, 1 to use leastsq optimizer
        
    :return: list, refined parameter
    '''
    bak = {}
    for opt in ['uncertaintyenable', 'integrationspace', 'qmax', 'qstep']:
        bak[opt] = getattr(srx.config, opt)
    
    xycenter = [int(srx.config.xbeamcenter), int(srx.config.ybeamcenter)]
    
    srx.updateConfig(uncertaintyenable=False,
                     integrationspace='qspace',
                     # qmax=qmax,
                     qstep=0.02)
    qind = [50, int(qmax / 0.02)]
    
    srx.prepareCalculation(pic=image)
    srxconfig = srx.config
    image = np.array(srx._getPic(image))
    
    func = partial(halfcut, srx=srx, image=image, qind=qind, mode=mode, output=output,
                   xycenter=xycenter, show=False)

    if mode == 'x':
        p0 = [srxconfig.xbeamcenter]
        bounds = (p0[0] - 3, p0[0] + 3)
    elif mode == 'y':
        p0 = [srxconfig.ybeamcenter]
        bounds = (p0[0] - 3, p0[0] + 3)
    elif mode == 'tilt':
        p0 = [srxconfig.tiltd]
        bounds = (p0[0] - 5, p0[0] + 5)
    elif mode == 'rotation':
        p0 = [srxconfig.rotationd]
        bounds = (0, 360)
    elif mode == 'all':
        p0 = [srxconfig.xbeamcenter, srxconfig.ybeamcenter, srxconfig.rotationd, srxconfig.tiltd]
        bounds = [[p0[0] - 2, p0[0] + 2], [p0[0] - 2, p0[0] + 2], [0, 360], [srxconfig.tiltd - 10, srxconfig.tiltd + 10]]
    elif mode == 'xy':
        p0 = [srxconfig.xbeamcenter, srxconfig.ybeamcenter]
        bounds = [[p0[0] - 3, p0[0] + 3], [p0[1] - 3, p0[1] + 3]]
    
    if output == 0:
        if mode != 'all':
            rv = minimize_scalar(func, bounds=bounds, method='Bounded')
            p = [rv.x]
        else:
            # rv = minimize(func, p0, method='L-BFGS-B', bounds=bounds, options={'xtol':0.001})
            rv = minimize(func, p0, method='Powell', bounds=bounds, options={'xtol':0.001})
            p = rv.x
    else:
        rv = leastsq(func, p0, epsfcn=0.001)
        p = rv[0]
    
    print p
    if mode == 'x':
        srx.updateConfig(xbeamcenter=p[0], **bak)
    elif mode == 'y':
        srx.updateConfig(ybeamcenter=p[0], **bak)
    elif mode == 'tilt':
        srx.updateConfig(tiltd=p[0], ** bak)
    elif mode == 'rotation':
        srx.updateConfig(rotation=p[0], ** bak)
    elif mode == 'all':
        srx.updateConfig(xbeamcenter=p[0], ybeamcenter=p[1], rotationd=p[2], tiltd=p[3], ** bak)
    return p

def selfCalibrate(srx, image, mode='full'):
    '''
    Do the self calibration
    
    the initial value is read from the current value of srx object, and the 
    refined results will be writrn into the srx object
    
    :param srx: SrXplanar object, object to do the integration
    :param image: str or 2d array, image to be calibrated
    :param mode: str:
        full: refine all parameters at once
        onebyone: refine x,y,tilt, rotation one by one
        xy: only refine x and y
        xyxy: refine x->y->xy
        
    :return: list, refined parameter
    '''
    p = []
    if mode == 'full':
        p = selfCalibrateX(srx, image, mode='all')
    elif mode == 'onebyone':
        p = selfCalibrateX(srx, image, mode='x')
        p = selfCalibrateX(srx, image, mode='y')
        p = selfCalibrateX(srx, image, mode='tilt')
        p = selfCalibrateX(srx, image, mode='rotation')
    elif mode == 'xy1':
        p = selfCalibrateX(srx, image, mode='x')
        p = selfCalibrateX(srx, image, mode='y')
    elif mode == 'xy2':
        p = selfCalibrateX(srx, image, mode='xy')
    elif mode == 'xyxy':
        p = selfCalibrateX(srx, image, mode='x')
        p = selfCalibrateX(srx, image, mode='y')
        p = selfCalibrateX(srx, image, mode='xyxy')
    return p
