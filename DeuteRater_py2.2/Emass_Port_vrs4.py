"""python port and modification of emass done by Bradley Naylor and Spencer Lofthouse 
Based on an algorithm developed by Alan L. Rockwood.

Published in 
Rockwood, A.L. and Haimi, P.: "Efficent calculation of 
Accurate Masses of Isotopic Peaks",
Journal of The American Society for Mass Spectrometry
JASMS 03-2263, in press

which contained the following copyright and disclaimer: 


Copyright (c) 2005 Perttu Haimi and Alan L. Rockwood

All rights reserved.

Redistribution and use in source and binary forms,
with or without modification, are permitted provided
that the following conditions are met:

    * Redistributions of source code must retain the
      above copyright notice, this list of conditions
      and the following disclaimer.
    * Redistributions in binary form must reproduce
      the above copyright notice, this list of conditions
      and the following disclaimer in the documentation
      and/or other materials provided with the distribution.
    * Neither the author nor the names of any contributors
      may be used to endorse or promote products derived
      from this software without specific prior written
      permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND
CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""

from collections import namedtuple
from copy import deepcopy
import Isotopomer_Class_vrs2 as IC
import numpy as np
from scipy.stats import pearsonr
from scipy.optimize import leastsq

sad = [] #name comes from Super Atom Data in the original emass program, this is the master list that holds all data throughout the calculations

#electorns only matter for charge.  Keep in mind this is for normal chemistry(charge means electrons move) ESI mass spectrometry may need changes
ELECTRON_MASS = .00054858
#obvious error mass to indicate issues
DUMMY_MASS = -10000000
PERCENT = .071
#takes a sequence strin(C2H5 for example) and turns it into a dictionary ( {'C':2, 'H':5})
"""NOTE: cannot handle multiple letter symbols like Al or Se.  Modify if such is needed"""
def parser(elem_comp):
    #initialize values
    letter = ''
    num = -100
    numstr = ''
    formmap = {} #formula map.  holdover from original program.
    for e in elem_comp:
        #if e is a letter we are done with numbers for the previous 3 letter
        if e.isalpha():
            #no point putting '':-100 into the dictionary
            if letter != '' and num >= 0:
                formmap[letter] = num
                num = -100
            letter = e
        elif unicode(e).isnumeric():
            if num < 0:
                numstr = e
            else:
                numstr += e
            num = float(numstr)
    #won't put last value in without this last command
    formmap[letter] = num
    return formmap

#combines two patterns (lists of peaks).  The idea is that small groups of atoms are combined into large atoms.  This function does the combination
"""math not understood do not fiddle with"""
def convolute_basic(g, f):
    h =[]
    g_n = len(g)
    f_n = len(f)
    if g_n == 0 or f_n == 0:
        return
    for k in range(g_n + f_n -1):
        sumweight = 0
        summass = 0
        start = 0 if k < f_n -1 else k - f_n +1 
        end = k if k < g_n -1 else g_n - 1
        for  i in range (start, end+1):
            weight = g[i].abundance * f[k-i].abundance
            mass = g[i].mass + f[k-i].mass
            sumweight += weight
            summass += weight * mass
        if sumweight == 0:
            p = isotope(DUMMY_MASS, sumweight)
        else:
            p = isotope(summass/sumweight, sumweight)
        h.append(p)
    return h
                
#f is a pattern (list of peaks) limit is what a relative value must be under to be kept in. default is zero if you want it higher, change limit(near the emass function)
def prune(f, limit):
    prune = []
    counter = 0
    for i in f:
        if i.abundance > limit:break
        prune.append(counter)
        counter += 1
    counter = len(f) -1
    for i in reversed(f):
        if i.abundance > limit: break
        prune.append(counter)
        counter -= 1
    for i in reversed(sorted(list(set(prune)))):
        del f[i]

#print_pattern is the output pattern.  name is a holdover from original emass, it does not print anymore
#the function normalizes the results so the highest is 100 (change if possible, extra function is inefficient)
#it will only add a value if the normalized value is higher than print_limit which is 5 *10^-7 by default
def print_pattern(result, digits):
    max_area = 0
    sum_area = 0
    for i in result:
        if max_area < i.abundance:
            max_area = i.abundance
        sum_area += i.abundance
    if max_area == 0:return
    print_limit = pow(10.0, -digits) /2
    mass_list =[]
    amount_list = []
    for i in result:
        val_perc = i.abundance/max_area *100
        if(i.mass != DUMMY_MASS and val_perc >= print_limit):
           mass_list.append(i.mass)
           amount_list.append(val_perc) 
    return mass_list, amount_list


#this function calculates the isotope pattern by using convolute basic a bunch of times. 
#tmp is an empty list for calculations(swapped with result when added to).
#fm 
def calculate(tmp, result, fm, limit, charge):
    for i in fm:
        sal = [deepcopy(master_isotope[i])]
        n = int(fm[i])
        j = 0
        #this while loop is run on the number of atoms of a certain type.  reduced by a rightward bit shift.
        while(n > 0):
            sz = len(sal)
            if(j == sz):
                sal.append([])
                sal[j] = convolute_basic(sal[j-1],  sal[j-1])
                prune(sal[j], limit)
            if n & 1:
                tmp = convolute_basic(result, sal[j])
                prune(tmp, limit)
                tmp, result = result, tmp #don't want to copy all elements, requires fixing
            n= n >>1
            j += 1
    #this code must be uncommented to use the charge state adjustments
    """for i in result:
        if charge > 0:
            i.mass = i.mass/abs(charge) - ELECTRON_MASS
        elif charge < 0:
            i.mass = i.mass/abs(charge) + ELECTRON_MASS"""
    return result
    
#standard function to normalize the peaks properly.
def normalize(old_list):
    new_list = []
    for thing in old_list:
        new_list.append(thing/sum(old_list))
    return new_list
    
#stores isotope data
isotope= namedtuple('isotope', ('mass', 'abundance'))    

#X starts at normal isotope frequencies(in this case H. X is positions that can be deuterated, not will be   
#original master_isotope = {'X':[isotope(1.0078246, 0.999844), isotope(2.0141021, 0.000156)], 'H':[isotope(1.0078246, 0.999844), isotope(2.0141021, 0.000156)], 'C': [isotope(12.0000000, 0.9891), isotope(13.0033554, 0.0109)], 'N': [isotope(14.0030732, 0.99635), isotope(15.0001088, 0.00365)], 'O': [isotope(15.9949141, 0.99759), isotope(16.9991322, 0.00037), isotope(17.9991616, 0.00204)], 'P': [isotope(30.973762, 1.0)], 'S':[isotope(31.972070, 0.9493), isotope(32.971456, 0.0076), isotope(33.967866, 0.0429), isotope(-1000000, 0), isotope(35.967080, 0.0002)]}
#NIST 
master_isotope = {'X':[isotope(1.0078250322, 0.999844), isotope(2.0141017781, 0.000156)], 'H':[isotope(1.0078250322, 0.999844), isotope(2.0141017781, 0.000156)], 'C': [isotope(12.0000000, 0.9891), isotope(13.003354835, 0.0109)], 'N': [isotope(14.003074004, 0.99635), isotope(15.000108899, 0.00365)], 'O': [isotope(15.994914620, 0.99759), isotope(16.999131757, 0.00037), isotope(17.999159613, 0.00204)], 'P': [isotope(30.973761998, 1.0)], 'S':[isotope(31.972071174, 0.9493), isotope(32.971458910, 0.0076), isotope(33.9678670, 0.0429), isotope(-1000000, 0), isotope(35.967081, 0.0002)]}
#protein prospector master_isotope = {'X':[isotope(1.00728, 0.9998), isotope(2.01355, 0.0001)], 'H':[isotope(1.00728, 0.9998), isotope(2.01355, 0.0001)], 'C': [isotope(11.99945, 0.9889), isotope(13.00281, 0.0111)], 'N': [isotope(14.00253, 0.9963), isotope(14.99956, 0.0037)], 'O': [isotope(15.99437, 0.9976), isotope(16.99858, 0.0004), isotope(17.99861, 0.002)], 'P': [isotope(30.97321, 1.0)], 'S':[isotope(31.97152, 0.9502), isotope(32.97091, 0.0075), isotope(33.96732, 0.0421), isotope(-1000000, 0), isotope(35.96653, 0.0002)]}
limit = 0
digits = 6

    
charge = 0
#fitting function.  fits the data fromt the loops in the main emass function to polynomials
def fitter(value_list, y_data, size, x, settings, filters, abund):
    #abund and neutromer spacing need differenc calculations
    if abund:
        extra_zeroes = [0,0,0,0] # need these for bigger peptides to line up the columns
        baseline = y_data[0] #graphs are comparison to baseline, so we need a baseline
        main = lambda p,x: p[0]*x**3 + p[1]*x**2 + p[2]*x #trinomial fit works well
        M0 = lambda p, x: -(p[0] -p[0]*np.exp(-p[1]*x)) #$try out new fit
            
        point_range = range(size)
        m0_start_attempt = [1,1]
        start_attempt = [1,1,1]
    else:
        point_range = range(1, size) # need to skip 0 (m0-m0 distance is irrelevant)
        main = lambda p,x: p[0]*x**4 + p[1]*x**3 + p[2]*x**2 +p[3]*x #need and 4th order polynomial
        extra_zeroes = [0,0,0,0,0]
        start_attempt = [1,1,1,1]
        # calculate the neutromer spacing baseline
        baseline = []
        for r in point_range:
            baseline.append(y_data[0][r]- y_data[0][0])
    value_list.extend(baseline)
    #more zeroes to line up output
    if size == filters["Peaks included if under mass cutoff"]:
        for r in range(int(filters["Peaks included if over mass cutoff"]-filters["Peaks included if under mass cutoff"])):
            value_list.append(0)
    for r in point_range:
        #need to generate y values for the x values
        y = []
        for row in y_data:
            if abund: y.append(row[r]- baseline[r]) #Abundance just need changes from baseline
            else: y.append((row[r]-row[0])-baseline[r-1]) #neutromer spacing needs to calculate distance and then compare that to baseline (the r-1 is because the zeroth term is m1-m0
        if abund and r == 0:
            coefficients, z_value = leastsq(lambda p,x,y : M0(p,x)-y, m0_start_attempt, args = (x, y))
        else:
            coefficients, z_value = leastsq(lambda p,x,y : main(p,x)-y, start_attempt, args = (x, y)) #need the error for leastsq fit (note that altering this to curve fit might simplify but should not change the results.)
        value_list.extend(coefficients) #add it up
        if abund and r == 0:
            value_list.append(pearsonr(y, M0(coefficients, x)))
        else: value_list.append(pearsonr(y, main(coefficients, x))) #get the pearsonr values.  This is often not useful, but can be useful for 
    if size == int(filters["Peaks included if under mass cutoff"]):
        for r in range(int(filters["Peaks included if over mass cutoff"]-filters["Peaks included if under mass cutoff"])):
            value_list.extend(extra_zeroes)
    return value_list
           
def emass(inqueue, outlist, error_list, AA_DICT, settings, filters):
    while not inqueue.empty():
        sequence = inqueue.get()
        label = settings["Heavy Element"]
        pep = IC.peptide(sequence,settings["Heavy Element"], AA_DICT)
        if pep.MW() > filters["mass cutoff"]: size = int(filters["Peaks included if over mass cutoff"])
        else: size  = int(filters["Peaks included if under mass cutoff"])
        fm = parser(pep.Composition(True)) #this turns the potential labeling sites into Xs so the program knows what they are
        tmp = []
        seq_data = []
        mz_data = []
        working = True
        x_range = np.arange(0.0,settings["Maximum Theoretical Percent"], settings["Step Size for Labeling"]) #this is used here and in the fitter.  easier to give it its own variable
        for x_pct in x_range:
            #increase x here
            #need to reassign since it is a tuple.  consider changing to dictionary or class in the future. 
            master_isotope['X'] = [isotope(master_isotope[label][0].mass, master_isotope[label][0].abundance-x_pct), isotope(master_isotope[label][1].mass, master_isotope[label][1].abundance+x_pct)]
            #does the calculations and saves the data
            result = [isotope(0, 1)]
            result = calculate(tmp, result, fm, limit, charge)
            mz, pre_norm  = print_pattern(result, digits)
            if x_pct == 0:
                true_m0 = mz[0]
            elif round(mz[0],2) != round(true_m0,2):
                working = False
                break
            norm = normalize(pre_norm[:size]) #need to normalize the abundance data (it comes out normalized with the highest peak as 1.  this makes the sumof the relative abundances in the number of relevant peaks 1)
            seq_data.append(norm)
            mz_data.append(mz[:size])
        if working:
            graph = [sequence, pep.Composition(False), pep.MW(), pep.get_n()] # save relevent data
            #run through fitter.  Do not use elif here.  it needs to check both so it will do both if both are selected
            if settings["Use Abundance"]:
                graph = fitter(graph, seq_data, size, x_range, settings, filters, True)
            if settings["Use neutromer spacing"]:
                graph = fitter(graph, mz_data, size, x_range, settings, filters, False)
            outlist.append(graph)  #add the data to the multiprocessing list
        else:
            error_list.append([sequence, x_pct])
        inqueue.task_done() 
