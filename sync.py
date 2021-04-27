#! /usr/bin/env python

from pyzotero import zotero as pyzotero
from pydash import _
import os
import subprocess
import shutil
from dotenv import load_dotenv
load_dotenv()

LIBRARY_TYPE = 'user'

# user config variables. set these in a .env
API_KEY = os.getenv('API_KEY')
LIBRARY_ID = os.getenv('LIBRARY_ID')
COLLECTION_NAME = os.getenv('COLLECTION_NAME') #in Zotero
FOLDER_NAME = os.getenv('FOLDER_NAME') #on the Remarkable device, this must exist!
STORAGE_BASE_PATH = os.getenv('STORAGE_BASE_PATH') #on local computer

RMAPI_CALL = "rmapi"
RMAPI_LS = "{} ls /{}".format(RMAPI_CALL, FOLDER_NAME)

zotero = pyzotero.Zotero(LIBRARY_ID, LIBRARY_TYPE, API_KEY)


def getCollectionId(zotero, collection_name):
    collections = zotero.collections(limit=200)
    for collection in collections:
        if (collection.get('data').get('name') == collection_name):
            return collection.get('data').get('key')


def getPapersTitleAndPathsFromZoteroCollection(zotero, collection_id, STORAGE_BASE_PATH):
    papers = []
    collection_items = [item for item in zotero.collection_items(collection_id) 
                        if item.get('data').get('contentType') == 'application/pdf']

    for item in collection_items:
        if item.get('data').get('linkMode') == 'linked_file':
            item_pdf_path = STORAGE_BASE_PATH + item.get('data').get('path')[12:]
            item_title = item.get('data').get('title')[:-4]
            if (item_pdf_path and item_title):
                papers.append({ 'title': item_title, 'path': item_pdf_path })
        elif item.get('data').get('linkMode') == 'imported_url':
            item_pdf_path = os.path.join(
                STORAGE_BASE_PATH,
                item.get('data').get('key'),
                item.get('data').get('filename')
            )
            item_title = os.path.basename(item_pdf_path)[:-4]
            if (item_pdf_path and item_title):
                papers.append({ 'title': item_title, 'path': item_pdf_path })

    return papers


def getPapersFromRemarkable(RMAPI_LS):
    remarkable_files = []
    for f in subprocess.check_output(RMAPI_LS, shell=True).decode("utf-8").split('\n'):
        if f and '[d]\t' not in f:
            remarkable_files.append(f.strip('[f]\t'))
    return remarkable_files


def getUploadListOfPapers(remarkable_files, papers):
    upload_list = []
    for paper in papers:
        title = paper.get('title')
        if title not in remarkable_files:
            upload_list.append(paper)
    return upload_list


def uploadPapers(papers):
    print("uploading {} papers".format(len(papers)))
    for paper in papers:
        path = paper.get('path')
        COMMAND = "{} put \"{}\" /{}".format(RMAPI_CALL, path, FOLDER_NAME)
        try:
            print(COMMAND)
            os.system(COMMAND)
        except:
            print("Failed to upload {}".format(path))


def downloadPapers(remarkable_files, zotero_papers):
    downloading_papers = []    
    for zotero_paper in zotero_papers:
        if zotero_paper["title"] in remarkable_files:
            downloading_papers.append(zotero_paper)

    print(f'downloading updated {len(downloading_papers)} papers')

    for downloading_paper in downloading_papers:
        paper_title = downloading_paper["title"]
        COMMAND = "{} geta /{}/\"{}\"".format(RMAPI_CALL, FOLDER_NAME, paper_title)
        try:
            print(COMMAND)
            subprocess.check_output(COMMAND, shell=True)
            shutil.move("{}-annotations.pdf".format(paper_title), downloading_paper["path"])
        except:
            print("No file or no annotations for {}".format(paper_title))
        
        if os.path.exists("{}.zip".format(paper_title)):
            os.remove("{}.zip".format(paper_title))



def getDeleteListOfPapers(remarkable_files, papers):
    delete_list = []
    paperNames = _(papers).map(lambda p: p.get('title')).value()
    for f in remarkable_files:
        if (f not in paperNames):
            delete_list.append(f)
    return delete_list


def deletePapers(delete_list):
    print("deleting {} papers".format(len(delete_list)))
    for paper in delete_list:
        COMMAND = "{} rm /{}/\"{}\"".format(RMAPI_CALL, FOLDER_NAME, paper)
        try:
            print(COMMAND)
            os.system(COMMAND)
        except:
            print("Failed to delete {}".format(paper))


def test_rmapi():
    try:
        _ = subprocess.call([RMAPI_CALL, "ls"], stdout=subprocess.DEVNULL)
    except FileNotFoundError as e:
        raise FileNotFoundError("Could not find rmapi binary {}".format(e))
    except Exception as e:
        raise e
    print("rmapi binary found and working")


def main():
    test_rmapi()

    print("------- sync started -------")
    collection_id = getCollectionId(zotero, COLLECTION_NAME)

    # get papers that we want from Zetero Remarkable collection
    papers = getPapersTitleAndPathsFromZoteroCollection(zotero, collection_id, STORAGE_BASE_PATH)
    print("{} papers in Zotero {} collection name".format(len(papers), COLLECTION_NAME))
    for paper in papers:
        print(paper.get('title'))

    # get papers that are currently on remarkable
    remarkable_files = getPapersFromRemarkable(RMAPI_LS)
    print("{} papers on Remarkable Device, /{}".format(len(remarkable_files), FOLDER_NAME))

    # download papers with annotations from remarkable
    downloadPapers(remarkable_files, papers)

    upload_list = getUploadListOfPapers(remarkable_files, papers)
    uploadPapers(upload_list)

    delete_list = getDeleteListOfPapers(remarkable_files, papers)
    deletePapers(delete_list)

    print("------- sync complete -------")


if __name__ == "__main__":
    main()
