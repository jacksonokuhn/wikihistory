#!/usr/bin/python

# Contains all function that involve the full Wikipedia history
#    and forming the model/graph

import argparse
import os
import requests
import networkx as nx

from newPatch import PatchSet, PatchModel

WIKI = 'https://en.wikipedia.org/'
LIMIT='1000'


def downloadHistory(title):
    """
        Downloads the full history of Wikipedia page, title, into
            full_histories
    """
    print "Downloading . . ."
    offset='0'
    i=0
    while offset!='1':
        print "Starting set " + str(i) + ". . ."
        i+=1
        offset=downloadPartial(title, offset)




def downloadPartial(title, offset):
    """
        Downloads up to 1000 revisions of a Wikipedia page, title
    """
    title=title.replace(' ', '_')
    api = WIKI+ 'w/index.php?title=Special:Export&pages=' + title + \
                '&offset='+offset+'&limit='+LIMIT+'&action=submit'

    if not os.path.isdir('full_histories'):
        os.mkdir('full_histories')
    if not os.path.isdir('full_histories/'+title):
        os.mkdir('full_histories/'+title)
    cachefile = 'full_histories/'+ title+'/'+title+'|'+offset+'.xml'
    
    file=open(cachefile, "w")
    
    # Download and save history
    r=requests.post(api, data="")
    last=True
    text=r.text.split('\n')
    for line in text:
        print line
        #line=line.encode("ascii", "ignore")
        if last:
            if line.strip()=='<page>':
                last=False
        else:
            if line.strip()[:11]=='<timestamp>':
                date=line.strip(' ')
                date=date[11:-12]
        file.write(line+'\n')
    file.close()
    if last:
        os.remove(cachefile)
        return '1'
    else:
        return date





def applyModel(title, remove):
    """
        Applies PatchModel to the history for Wikipedia page, title.
        Returns the full history tranformed into a graph according to the model,
            the PatchModel, and the most recent content.
    """

    title=title.replace(" ", "_")
    offset='0'

    # Make folders for model, graph, and content files
    if not os.path.isdir('GMLs'):
        os.mkdir('GMLs')
    if not os.path.isdir('models'):
        os.mkdir('models')
    if not os.path.isdir('content'):
        os.mkdir('content')

    # Get the list of vertices to remove
    if remove:
        remList = getRemlist(title)

    print "Applying model . . ."

    model = PatchModel()
    prev = []
    pid=0
    
    getid = True # can read id from doc
    gettime = False # have id ready to use, can read time from doc 
    gettext= False   # have an id ready to use
    compare = False  # ready to compare content
    writeText= False  # adding to current content

    while os.path.isfile('full_histories/'+title+'/'+title+'|'+offset+'.xml'):
        historyFile=open('full_histories/'+title+'/'+title+'|'+offset+'.xml', "r")

        line = historyFile.readline().strip()
        while line[:4] != "<id>":
            line=historyFile.readline().strip()

        for line in historyFile:
            line=line.strip()

            # Gets the next valid revision id
            if getid:
                if line[:4] == "<id>":
                    rvid = line[4:-5]
                    if remove and rvid in  remList: 
                        remList.remove(rvid)
                    else:
                        getid=False
                        gettime=True
            if gettime:
                if line[:11] == "<timestamp>":
                    timestamp = line[11:-12]
                    offset=timestamp
                    gettime = False
                    gettext=True

            # Have an id ready to use, looking for start of content
            if gettext:
                if line[:5] == "<text":
                    content= ""
                    line = line.split('">')
                    if len(line) == 1:
                        line += [""]
                    line = line[1]+"\n"
                    gettext=False
                    writeText=True
        
            # Have reached start if content, looking for end
            if writeText:
                if line[-7:] == "</text>":
                    content+=line[:-7]
                    writeText=False
                    compare = True
                else:
                    content+=line+"\n"
        
            # Have text ready to compare. 
            # Apply to the PatchModel and write dependencies to graph.
            if compare:
                contentList=content.split()
                ps = PatchSet.psdiff(pid, prev, contentList)
                pid+=len(ps.patches)
                for p in ps.patches:
                    model.apply_patch(p, timestamp) #list of out-edges from rev
            
                prev = contentList
                compare = False
                getid = True

        
        historyFile.close()

    if remove:
        cachefile = title.replace(" ", "_")+'_rem.txt'
    else:
        cachefile = title.replace(" ", "_")+'.txt'

    # Writes graph to file
    nx.write_gml(model.graph, "GMLs/"+cachefile)
        
    # Write model to file
    modelFile = open("models/"+ cachefile, "w")
    line = ""
    for patch in model.model:
        line+= str(patch[0])+' '+str(patch[1])+'\n'
    modelFile.write(line)
    modelFile.close()

    # Write content to file
    contentFile = open("content/"+ cachefile, "w")
    contentFile.write(content)
    contentFile.close()
    
    return model.graph, content, model.model




def getRemlist(title):
    """
        Gets a list of ids of revisions that are bot reverts
        or that were reverted by bots
    """
    print "Removing bot rv."
    offset='0'
    remList = []
    
    while os.path.isfile('full_histories/'+title+'/'+title+'|'+offset+'.xml'):
        
        file = open('full_histories/'+title+'/'+title+'|'+offset+'.xml', "r")
        
        username=False
    
        for line in file:
            line=line.strip()

            if not username and line[:4] == "<id>":
                rvid = line[4:-5]

            if line[:10] == "<username>":
                username=True
            else:
                username=False

            if line[:10] == "<parentid>":
                parentid=line[10:-11]

            elif line[:11]=='<timestamp>':
                offset=line[11:-12]

            elif line[:9]=="<comment>":
                if "BOT - rv" in line:
                    remList.append(rvid)
                    remList.append(parentid)

        file.close()
    return remList




def readGraph(title, remove):
    """
        Reads a networkx graph from a file for Wikipedia page, title, with
            remove 
    """
    print "Reading graph . . ."
    if remove:
        file = "GMLs/" + title.replace(" ", "_")+'_rem.txt'
    else:
        file = "GMLs/" + title.replace(" ", "_")+'.txt'

    assert os.path.isfile(file), "Graph file does not exist."

    return nx.read_gml(file)




def readContent(title, remove):
    """
        Reads and returns a string from a file
    """
    print "Reading content . . ."

    if remove:
        file = "content/"+title.replace(" ", "_")+"_rem.txt"
    else:
        file = "content/"+title.replace(" ", "_")+".txt"

    assert os.path.isfile(file), "Content file does not exist."

    contentFile = open(file, "r")
    content = ""
    for line in contentFile:
        content+=line
    contentFile.close()
    return content




def readModel(title, remove):
    """
        Reads and returns a PatchModel from a file
    """
    print "Reading model . . ."
    if remove:
        file = "models/"+title.replace(" ", "_")+"_rem.txt"
    else:
        file = "models/"+title.replace(" ", "_")+".txt"

    assert os.path.isfile(file), "Model file does not exist."

    modelFile = open(file, "r")
    model=[]

    # Read model
    for line in modelFile:
        line=line.split()
        model.append((int(line[0]), int(line[1])))
    modelFile.close()
    return model




def wiki2graph(title, remove, new):
    """
        Returns a networkx graph, the content of the latest revision, and the 
            PatchModel for Wikipedia page, title.
        Setting remove to True removes bot reverses and vandalism from the data.
        Setting new to True applies the model whether or not it is cached
    """
    if remove:
        file = title.replace(" ", "_")+"_rem.txt"
    else:
        file = title.replace(" ", "_")+".txt"

    # Check if files exist to avoid reapplying model
    if not new and \
        os.path.isdir('GMLs') and os.path.isfile("GMLs/"+file) and \
        os.path.isdir('content') and os.path.isfile("content/"+file) and \
        os.path.isdir('models/') and os.path.isfile("models/"+file):

        graph = readGraph(title, remove)
        content = readContent(title, remove)
        model = readModel(title, remove)

    # Apply model. Download full history if necessary
    else:
        file = title.replace(" ", "_")
        if not os.path.isdir('full_histories') or not os.path.isdir("full_histories/"+title.replace(' ', '_')):
            downloadHistory(title)
        (graph, content, model) = applyModel(title, remove)

    return graph, content, model





def parse_args():
    """parse_args parses sys.argv for wiki2graph."""
    # Help Menu
    parser = argparse.ArgumentParser(usage='%prog [options] title')
    parser.add_argument('title', nargs=1)
    parser.add_argument('-r', '--remove',
                      action='store_true', dest='remove', default=False,
                      help='remove mass deletions')
    parser.add_argument('-n', '--new',
                      action='store_true', dest='new', default=False,
                      help='reapply model even if cached')

    n=parser.parse_args()

    wiki2graph(n.title[0], n.remove, n.new)


if __name__ == '__main__':
    parse_args()
