
# function to quickly calculate the means and means sums of squares of
# all the partitions of a set of points

import cPickle
import numpy
from math import pi
from scipy import array
from mpmath import log, gamma, mpf # arbitrary float precision!
import sys

def load_testdata( filename = "trajectory.dat" ):
	FILE = open( filename )
	u = cPickle.Unpickler( FILE )
	data = u.load()
	FILE.close()
	return data

# for Gaussian noise only. For this reason, the first three points and the last two points
# cannot correspond to a change point. Thus, we return an array of length (npts-5).
def calc_mean_mss( data ):
	#data = numpy.array( data, "float64" )
	npts = len( data )

	#initialize
	data2=data**2
	dataA=data[0:3]
	dataA2=data2[0:3]
	NA = len(dataA)
	dataB=data[3:]
	dataB2=data2[3:]
	NB = len(dataB)

	sumA=dataA.sum() ; sumsqA=dataA2.sum()
	sumB=dataB.sum()  ; sumsqB=dataB2.sum()

	mean_var_array=[]

	# first data point
	meanA=sumA/NA  
	meanB=sumB/NB
	meansumsqA = sumsqA/NA
	meansumsqB = sumsqB/NB
	meanA2 = meanA**2
	meanB2 = meanB**2
	sA2=meansumsqA-meanA2
	sB2=meansumsqB-meanB2
	mean_var_array.append( (3, meanA2, sA2, npts-3, meanB2, sB2 ) )

	for i in range( 3, npts-3 ):
		NA += 1	; NB -= 1
		next = data[i]
		sumA += next	; sumB -= next
		nextsq = data2[i]
		sumsqA += nextsq; sumsqB -= nextsq

		meanA=sumA/NA
		meanB=sumB/NB
		meansumsqA=sumsqA/NA
		meansumsqB=sumsqB/NB
		meanA2=meanA**2
		meanB2=meanB**2
		sA2=meansumsqA-meanA2
		sB2=meansumsqB-meanB2
		mean_var_array.append( (NA, meanA2, sA2, NB, meanB2, sB2) )
	
	return mean_var_array

# uses calc_mean_mss() to compute the relative weights of the switch time
def calc_twostate_weights( data ):
	weights=[0,0,0] # the change cannot have occurred in the last 3 points
	means_mss=calc_mean_mss( data )

	i=0
	try:
		for nA, mean2A, varA, nB, mean2B, varB in means_mss :
			#print "computing for data", nA, mean2A, varA, nB, mean2B, varB
			numf1 = calc_alpha( nA, mean2A, varA )
			numf2 = calc_alpha( nB, mean2B, varB )
			denom = (varA + varB) * (mean2A*mean2B)
			weights.append( (numf1*numf2)/denom) 
			i += 1
	except:
		print "failed at data", i # means_mss[i]
		print "---"
		#print means_mss
		print "---"
		raise

	weights.extend( [0,0] ) # the change cannot have occurred at the last 2 points
	return array( weights )

def calc_alpha( N, x2, s2 ):
	first = mpf(N)**(-N/2.0 + 1.0/2.0)
	second = mpf(s2)**(-N/2.0 + 1.0 )
	third = gamma( mpf(N)/2.0 - 1.0 ) 
	return first*second*third

def findGaussianChangePoint( data ):
	
	# the denominator. This is the easy part.
	N = len( data )

	if N<6 : return None # can't find a cp in data this small

	# set up gamma function table
	#for i in range(N):
		

	s2 = mpf(data.var())
	gpart = gamma( mpf(N)/2.0 - 1 )
	denom = (pi**1.5) * mpf((N*s2))**( -N/2.0 + 0.5 ) * gpart

	# the numerator. A little trickier.
	# calc_twostate_weights() already deals with ts<3 and ts>N-2.
	weights=calc_twostate_weights( data )
	if weights is None: return None

	num = 2.0**2.5 * abs(data.mean()) * weights.mean()

	logodds = log( num ) - log( denom ) 	

	print "num:", num, "log num:", log(num), "| denom:", denom, "log denom:", log(denom), "|| log odds:", logodds 
	
	# If there is a change point, then logodds will be greater than 0
	if logodds < 0 : 
		return None
	
	return ( weights.argmax(), logodds ) 

class ChangePointDetector:
	def __init__( self, data, function ):
		self.data = data
		self.datalen = len( self.data )
		self.function = function
		self.changepoints = []
		self.logodds = {}
		self.niter = 0
		self.maxiter = 1000000 # just in case

	def nchangepoints( self ):
		return len( self.changepoints )

	def split_init( self, verbose=False ):
		self.split( 0, self.datalen, verbose )

	def split( self, start, end, verbose=False ):
		if self.niter > self.maxiter :
			print "Change point detection error: number of iterations exceeded"
			print "If this is the right result, you may need to increase"
			print "ChangePointDetector.maxiter (currently %d)" % self.maxiter
			return
		self.niter += 1
		if verbose:
			print "\nIteration %d" % self.niter
			print "Trying to split the segment:", self.data[start:end], "(data from %d to %d)" % ( start, end)
			print self.data[start:end]

		# try to find a change point in the data segment 
		try:
			result = self.function( self.data[ start: end ] )	
		except TypeError: 
			print "trying to test data from %d to %d failed" % ( start,end )
			#print self.data
			raise

		# otherwise, store the cp and call self.split on the two ends
		if result is not None :
			try: # fails if only one value is returned
				logodds = result[1]
				self.logodds[ start+result[0] ] = logodds
				result = start+result[0]
			except TypeError: # must mean it's one number?
				result += start

			if verbose: print "!! change point detected at %d !!" % result
			self.changepoints.append( result )
			self.split( start, result, verbose )
			self.split( result+1, end, verbose )

	def sort( self ): self.changepoints.sort()

	# display the change points
	def show( self ): print self.changepoints

	# show the change points along with the log odds
	def showall( self ):
		for i in range( len( self.changepoints ) ) :
			changepoint = self.changepoints[i]
			try: 
				logodds = self.logodds[ changepoint ]
			except KeyError:
				logodds = None
			print "%d (%f)" % ( changepoint, logodds )

	def largest_logodds( self ):
		return array( self.logodds.values() ).max()
