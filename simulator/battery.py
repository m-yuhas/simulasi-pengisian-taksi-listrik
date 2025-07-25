import numpy

from scipy import interpolate


class BrevoModel:

    def __init__(self, capacity, soc):
        self.alpha = [2897.8, 2694.3]
        self.beta = [7413.1, 6025.6]
        self.E_a = 31500
        self.R_g = 8.314
        self.eta = 152.6
        self.z = 0.4
        self.ocv = []
        self.r_bat = []

        # TODO: Implement calender degredation

        # capacity in kWh
        # soc in %
        self.initial_capacity = capacity
        self.actual_capacity = capacity
        self.soc = soc

    def recalculate_capacity(delta_W, delta_t, ambient_t):
        # I_c in 1/h
        # Q_acc in A*s
        # delta_t in s
        # delta_W in kWh
        # ambient_T in C
        self.soc = min(max(delta_W / self.actual_capacity + self.soc * self.actual_capacity, 1.0), 0.0)

        s = numpy.array([0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9])
        t = numpy.array([-15.0, 0.0, 30.0])
        r = numpy.array([
            [1.340, 1.080, 0.320],
            [1.340, 1.080, 0.200],
            [1.340, 1.080, 0.150],
            [1.340, 0.300, 0.125],
            [0.680, 0.250, 0.125],
            [0.485, 0.260, 0.130],
            [0.430, 0.250, 0.130],
            [0.415, 0.240, 0.160],
            [0.420, 0.255, 0.165],
            [0.430, 0.260, 0.130],
            [0.440, 0.270, 0.130]
        ])
        i_tmp = interpolate.RegularGridInterpolator((s, t), r)
        R_bat = i_tmp(numpy.array([self.soc, ambient_t]))
        OCV = numpy.interp(self.soc, [0.00, 0.20, 0.50, 0.90, 1.00], [333.0, 351.0, 364.0, 388.0, 400.0])
        I_bat = (-OCV + numpy.sqrt(OCV ** 2 + 4 * 3600 * 1000 * (abs(delta_W) / delta_t) * R_bat))/(2 * R_bat)
        Q_acc = I_bat * delta_t
        I_c = (abs(delta_W) / self.actual_capacity) / (3600 * delta_t)
        sigma_fcn = (self.alpha * self.soc - self.beta) * numpy.exp((-self.E_a + self.eta * I_c)/(self.R_g*(273.15 + ambient_t)))
        tau_alpha = 1 - sigma_fcn * Q_acc ** self.z
        self.actual_capacity = tau_alpha * self.actual_capacity
        
