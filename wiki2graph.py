#!/usr/bin/python


# Contains all function that involve the full Wikipedia history
#    and forming the model/graph

import argparse
import os
import pickle
import textProcessor as proc
import networkx as nx
from Patch import PatchSet, PatchModel
##
# Wiki options
WIKI = 'https://en.wikipedia.org/'
LIMIT='1000'



def applyModel(title, remove, new):
    """
        Applies PatchModel to the history for Wikipedia page, title.
        Returns the full history tranformed into a graph according to the model,
            the PatchModel, and the most recent content.
    """

    title=title.replace(' ', '_')

    # Make folders for model and graph files
    if not os.path.isdir('GMLs'):
        os.mkdir('GMLs')
    if not os.path.isdir('models'):
        os.mkdir('models')

    print ('Setting up distance comparison . . .')
    
    #if not os.path.isdir('full_histories') or not os.path.isdir('full_histories/'+title):
    #    proc.cleanCorpus(title)

    # Set up semantic distance comparison
    if not new:
        dictionary = (proc.saveAndReturnDictionary(title, remove)
                      if not os.path.isdir('dictionaries') or not os.path.isfile('dictionaries/'+title+'.dict')
                      else proc.readDictionary(title))
        
        corpus = (proc.saveAndReturnCorpus(title, dictionary)
                  if not os.path.isdir('corpus') or not os.path.isfile('corpus/'+title+'.mm')
                  else proc.readCorpus(title))
        
        tfidf = (proc.saveAndReturnTfidf(title, corpus, True)
                 if not os.path.isdir('tfidf') or not os.path.isfile('tfidf/'+title+'.tfidf')
                 else proc.loadTfidf(title))

        lsi = (proc.saveAndReturnLsi(title, tfidf, corpus, dictionary, 300)
               if not os.path.isdir('lsi') or not os.path.isfile('lsi/'+title+'.lsi')
               else proc.loadLsi(title))
    else:
        dictionary = proc.saveAndReturnDictionary(title)
        corpus = proc.saveAndReturnCorpus(title, dictionary)
        tfidf = proc.saveAndReturnTfidf(title, corpus, True)
        lsi = proc.saveAndReturnLsi(title, tfidf, corpus, dictionary, 300)


    # Get the list of vertices to remove
    """
    if remove:
        remList = proc.getRemlist(title)
    """

    print ('Applying model . . .')

    model = PatchModel()
    prev = ''
    pid=0
    wikiit=proc.WikiIter(title, remove)
    set_id = 0
    model_dict = {}
    first_id = None
    cur_id = None
        directory = 'models/'+title+'_rem/' if remove else 'models/'+title+'/'
    if not os.path.isdir(directory):
        os.makedirs(directory)
    for (rvid, timestamp, content) in wikiit.__iter__():
       
        # Apply to the PatchModel and write dependencies to graph.
        """
        if remove and rvid in remList:
            remList.remove(rvid)
        """

        else:
            if first_id is None:
                first_id = rvid
            cur_id = rvid
            # Get semantic distance
            dist = 1 - proc.scoreDoc(title, prev, content, dictionary, tfidf, lsi)[0][1]

            # Apply PatchModel
            #content=content.encode('ascii', 'replace')
            content_split=content.split()
            prev_split=prev.split()
            ps = PatchSet.psdiff(pid, set_id, prev_split, content_split)
            pid+=len(ps.patches)
            set_id += 1
            for p in ps.patches:
                model.apply_patch(p, timestamp, dist) #list of out-edges from rev
            
            prev = content
            model_dict[(rvid)] = model.model

            if len(model_dict) >= 50000: #for if this ever needs to get split up
                with open(directory+title+'|'+first_id+'|'+cur_id+'.pickle', 'wb') as handle:
                    pickle.dump(model_dict, handle, protocol=pickle.HIGHEST_PROTOCOL)
                first_id = None
                model_dict = {}
    # Writes graph to file
    nx.write_gml(model.graph, 'GMLs/'+title+'.txt')
        
    # Write model to file
    if len(model_dict) > 0:
        with open(directory+title+'|'+first_id+'|'+cur_id+'.pickle', 'wb') as handle:
            pickle.dump(model_dict, handle, protocol=pickle.HIGHEST_PROTOCOL)
    with open(directory+title+'_cur.pickle', 'wb') as handle:
        pickle.dump(model.model, handle, protocol=pickle.HIGHEST_PROTOCOL)

    
    return model.graph, content, model.model


def readGraph(title, remove):
    """
        Reads a networkx graph from a file for Wikipedia page, title, with
            remove 
    """
    print ('Reading graph . . .')

    title=title.replace(' ', '_')

    file = 'GMLs/' + title+'_rem.txt' if remove else 'GMLs/' + title+'.txt'

    assert os.path.isfile(file), 'Graph file does not exist.'

    return nx.read_gml(file, label='id')




def getContent(title, timestamp=None):
    """
        Reads and returns a string from a file
    """
    return proc.getContent(title, timestamp)


def getRaw(title, timestamp=None):
    """
        Reads and returns a string from a file
    """
    return proc.getRaw(title, timestamp)
    

def readModel(title, remove, rvid=None):
    """
        Reads and returns a PatchModel from a file
    """
    print ('Reading model . . .')

    title = title.replace(' ', '_')

    directory = 'models/'+title+'_rem/' if remove else 'models/'+title+'/'

    if rvid is None:
        filename = directory+title+'_cur.pickle'
        assert os.path.isfile(filename), 'Model file does not exist.'

        with open(filename, 'rb') as handle:
            model = pickle.load(handle)
    else:    
        for filename in os.listdir(directory):
            to_split = filename.replace('.', '|')
            split_name = to_split.split('|')
            if split_name[1] <= rvid <= split_name[2]:
                with open(directory+filename, 'rb') as handle:
                    model_dict = pickle.load(handle)

        model = model_dict[rvid]

    assert model is not None, 'Model does not exist.'

    return model



def wiki2graph(title, remove, new, download):
    """
        Returns a networkx graph, the content of the latest revision, and the 
            PatchModel for Wikipedia page, title.
        Setting remove to True removes bot reverses and vandalism from the data.
        Setting new to True applies the model whether or not it is cached
    """
    title = title.replace(' ', '_').lower()
    file = title+'.txt'

    model_dir = 'models/'+title+'_rem' if remove else = 'models/' + title

    # Check if files exist to avoid reapplying model
    if not new and \
        os.path.isdir('GMLs') and os.path.isfile('GMLs/'+file) and \
        os.path.isdir(model_dir):

        graph = readGraph(title, remove)
        model = readModel(title, remove)


    # Apply model. Download full history if necessary
    else:
        if not os.path.isdir('full_histories') or not \
        os.path.isdir('full_histories/'+title) or not \
        proc.checkCollection(title) or download:
            proc.downloadAndExtractHistory(title)

        graph, content, model = applyModel(title, remove, new)

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
    parser.add_argument('-d', '--download',
                      action='store_true', dest='download', default=False,
                      help='download and extract new data')

    n=parser.parse_args()

    wiki2graph(n.title[0], n.remove, n.new, n.download)


if __name__ == '__main__':
    parse_args()
