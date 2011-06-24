#!/usr/bin/python

import os
import time
import pickle
import getopt
import urllib
from SimpleClient import SimpleClient
import cloudwatch

## AWS credential , IAM is usefull :)
AWS_ACCESS_KEY_ID = 'YOUR_ACCESS_KEY_ID_HERE'
AWS_SECRET_ACCESS_KEY = 'YOUR_SECRET_ACCESS_KEY_HERE'

## If you want to get all all query-items then set QLIST = ['ALL']
#QLIST = ['ALL']
## If not, you may set individual indiviaul items
QLIST = [ 'cpu', 'memory' ]

# DATA TYPE work file
STATEFILE = '/var/tmp/cloudwatch-munin-node.state'

# Get instance-id from meta-data
api_ver = '2011-01-01'
base_url = 'http://169.254.169.254/%s/meta-data' % api_ver
instance_id = urllib.urlopen('%s/instance-id/' % base_url).read()

# Open local munin-node
m = SimpleClient('localhost', 4949)

# check node names (at this time, variable is not used)
nodename = []
m.writeline('nodes')
while True:
    l = m.readline()
    if not l:
        break
    if l.startswith('.'):
        break
    nodename.append(l.rstrip())

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
        l = m.readline()
        if not l:
            break
        if l.startswith('.'):
            break
        mcdict[item].append(l.rstrip())

    mfdict[item] = []
    m.writeline('fetch' + item)
    while True:
        l = m.readline()
        if not l:
            break
        if l.startswith('.'):
            break
        mfdict[item].append(l.rstrip())

# Close munin-node
m.writeline('quit')

# Init connection to cloudwatch
cw = cloudwatch.connection(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY) 

# Init item old value dictionary
movalue = {}
if not os.path.exists(STATEFILE):
    f = open(STATEFILE, 'w')
    pickle.dump(movalue, f)
    f.close()

# Read old derive value
f = open(STATEFILE)
movalue = pickle.load(f)
f.close()

# Init item new value dictionary
mnvalue = {}

# Set Time
newtime = time.time()
oldtime = newtime
mnvalue['cwfetchtime'] = newtime
mwtime = 0.0
if 'cwfetchtime' in movalue:
    oldtime = movalue['cwfetchtime']
    mwtime = newtime - oldtime

# Init item data type dictionary
mdtype = {}

# Init item cdef dictionary
mcdef = {}

# Loop
for mitem in QLIST:
    # checking item upper-limit (is percentage? (at this time, variable is not used)
    # checking item lower-limit (at this time, variable is not used)
    # checking item unit is SI or binary (has base is 1024 ?) (at this time, variable is not used)
    # checking item type GAUGE, DERIVE, COUNTER, ABSOLUTE
    upperlimit = -1
    lowerlimit = -1
    mbase = 1000
    munit = 'None'
    for mc in mcdict[mitem]:
        if mc.startswith('graph_args'):
            args = mc.split()
            args.remove('graph_args')
            optlist, args = getopt.getopt(args, 'l:u:r', ['base=', 'lower-limit=', 'upper-limit=',
                                                          'logarithmic', 'rigid', 'units-exponent='])
            for wo, wa in optlist:
                if wo in ('-u', '--upper-limit'):
                    # some plugins has bug
                    ws = wa.rstrip(';')
                    upperlimit = int(ws)
                    munit = 'Percent'
                if wo in ('-l', '--lower-limit'):
                    ws = wa.rstrip(';')
                    lowerlimit = int(ws)
                if wo in ('--base'):
                    ws = wa.rstrip(';')
                    mbase = int(ws)

        # Set tiem data type GAUGE, DERIVE, COUNTER, ABSOLUTE
        mconfig = mc.split()
        if mconfig[0].endswith('.type'):
            mcdata = mconfig[0].split('.')
            mname = mitem + '_' + mcdata[0]
            mdtype[mname] = mconfig[1]

        # tiem has cdef?
        mconfig = mc.split()
        if mconfig[0].endswith('.cdef'):
            mcdata = mconfig[0].split('.')
            mname = mitem + '_' + mcdata[0]
            mwcdef = mconfig[1].split(',')
            mcdef[mname] = mwcdef

    # Making data
    mwval = 0.0
    for val in mfdict[mitem]:
        mval = 0.0
        nv = val.split()
        mn = nv[0].split('.')
        mname = mitem + '_' + mn[0]
        itemtype = 'GAUGE'
        if mname in mdtype:
            itemtype = mdtype[mname]
        if nv[1] != 'U':
            mval = float(nv[1])
        if itemtype != 'GAUGE':
            mnvalue[mname] = mval
            if mname in movalue and mwtime > 0.0:
                if itemtype == 'ABSOLUTE':
                    mwval = mval
                else:
                    # itemtype is 'DERIVE' or 'COUNTER'
                    moval = float(movalue[mname])
                    mwval = mval - moval
                    if itemtype == 'COUNTER':
                        if mwval < 0.0:
                            if moval < 4294967296.0:
                                # width 32bit
                                mwval += 4294967296.0
                            else:
                                # width 64bit
                                mwval += 18446744073709551615.0
                # Calc rate
                mval = mwval / mwtime
            else:
                # missing old data? or first time? value is 'U', force set 0.0
                mval = 0.0

        # If item has cdef?
        if mname in mcdef:
            mcval = float(mcdef[mname][1])
            mcope = mcdef[mname][2]
            if mcval != 0.0:
                if mcope == '+':
                    mval = mval + mcval
                elif mcope == '-':
                    mval = mval - mcval
                elif mcope == '*':
                    mval = mval * mcval
                elif mcope == '/':
                    mval = mval / mcval

        # Put cloudwatch
        #print 'InstanceId:', instance_id, 'MetricName: ', mname, 'Unit: ', munit, 'Value: ', str(mval), 'Type: ', itemtype
        cw.putData('MUNIN', 'InstanceId', instance_id, mname, munit, mval)


# Store item new value dictionary
f = open(STATEFILE, 'w')
pickle.dump(mnvalue, f)
f.close()
