#!/usr/bin/python

import string
import getopt
import urllib
import httplib2, simplejson
from SimpleClient import SimpleClient
import cloudwatch

## AWS credential , IAM is usefull :)
AWS_ACCESS_KEY_ID = 'YOUR_ACCESS_KEY_ID_HERE'
AWS_SECRET_ACCESS_KEY = 'YOUR_SECRET_ACCESS_KEY_HERE'

## If you want to get all all query-items then set QLIST = ['ALL']
#QLIST = ['ALL']
## If not, you may set individual indiviaul items
QLIST = [ 'cpu', 'memory' ]

# Get instance-id from meta-data
api_ver = '2011-01-01'
base_url = 'http://169.254.169.254/%s/meta-data' % api_ver
instance_id = urllib.urlopen('%s/instance-id/' % base_url).read()

# Open local munin-node
m = SimpleClient('localhost', 4949)

# check node names (at this time, not use)
nodename = []
m.writeline('nodes')
while True:
    line = m.readline()
    if not line:
        break
    if line.startswith('.'):
        break
    nodename.append(line.rstrip())

# Get all query-items
if QLIST[0] == 'ALL':
    m.writeline('list')
    QLIST = m.readline().split()

# Init munin config dictionary, munin fetch dictionary
mcdict = {}
mfdict = {}
for item in QLIST:
    mcdict[item] = []
    m.writeline('config' + item)
    while True:
        line = m.readline()
        if not line:
            break
        if line.startswith('.'):
            break
        mcdict[item].append(line.rstrip())

    mfdict[item] = []
    m.writeline('fetch' + item)
    while True:
        line = m.readline()
        if not line:
            break
        if line.startswith('.'):
            break
        mfdict[item].append(line.rstrip())

# Close munin-node
m.writeline('quit')

# Init connection to cloudwatch
cw = cloudwatch.connection(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY) 

# Init munin item value summary dictionary
mvsum = {}

# Loop
for mitem in QLIST:
    # checking item is percentage? (has upper-limit ?)
    # checking item unit is SI or binary (has base is 1024 ?) (at this time, not use)
    upperlimit = -1
    mbase = 1000
    isga = -1
    for mc in mcdict[mitem]:
        isga = mc.find('graph_args')
        if isga != -1:
            args = mc.split()
            args.remove('graph_args')
            optlist, args = getopt.getopt(args, 'l:u:r', ['base=', 'lower-limit=', 'upper-limit=',
                                                          'logarithmic', 'rigid', 'units-exponent='])
            for wo, wa in optlist:
                if wo in ('-u', '--upper-limit'):
                    upperlimit = int(wa)
                if wo in ('--base'):
                    mbase = int(wa)
                    
    # If is this item value percentage?, then make sum
    if upperlimit != -1:
        mvsum[mitem] = 0.0
        for val in mfdict[mitem]:
            nv = val.split()
            mvsum[mitem] += float(nv[1])
            
    # Making data
    mval = 0.0
    munit = 'None'
    for val in mfdict[mitem]:
        nv = val.split()
        mn = nv[0].split('.')
        mname = mitem + '_' + mn[0]
        mval = float(nv[1])
        if upperlimit != -1:
            munit = 'Percent'
            mval = (mval * float(upperlimit)) / mvsum[mitem]

        # Put cloudwatch
        #print 'InstanceId:', instance_id, 'MetricName: ', mname, 'Unit: ', munit, 'Value: ', str(mval)
        cw.putData('MUNIN', 'InstanceId', instance_id, mname, munit, mval)


