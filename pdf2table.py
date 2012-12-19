#!/usr/bin/python2.7

import sys
import os
import argparse
import itertools

# A fair bit of motivation for this is derived from:
#   1. The makers tutorial page
#       www.unixuser.org/~euske/python/pdfminer/programming.html
#   2. An indepth discussion by Denis of his disecting of pdfs
#       denis.papathanasiou.org/?p=343

from pdfminer.pdfparser import PDFParser, PDFDocument
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfdevice import PDFDevice
from pdfminer.layout import LAParams, LTTextBox, LTTextLine
from pdfminer.converter import PDFPageAggregator

def main(argv):

    config = parse_config(argv[1:])

    with open(config.input, 'rb') as infile:
        parser = PDFParser(infile)
        doc    = PDFDocument()
        parser.set_document(doc)
        doc.set_parser(parser)
        doc.initialize()

        assert doc.is_extractable

        for page in extract_text(doc, config):
            organize_page(page)

    return 0

def organize_page(page):
    for coord, line in sorted(page):
        print coord, line

def extract_text(doc, config):
    rsrcmanager = PDFResourceManager()
    laparams = LAParams()
    device = PDFPageAggregator(rsrcmanager, laparams=laparams)
    interpreter = PDFPageInterpreter(rsrcmanager, device)

    pages = doc.get_pages()

    if config.page is not None:
        #take only 1 page
        #note: Use page-1 because of 0 index (where pdfs index from 1)
        pages = [ next(itertools.islice(pages, config.page-1, None), None) ]

    for page in pages:
        interpreter.process_page(page)
        layout = device.get_result()

        text = []
        #print dir(layout)
        #print layout.objs
        for obj in layout:
            if isinstance(obj, LTTextBox):
                #print('({}. {}), ({}, {})'.format(obj.x0, obj.y0, obj.x1, obj.y1))
                #print obj.get_text()
                for line in obj:
                    coord = ((line.x0, line.y0), (line.x1, line.y1))
                    text.append((coord, line.get_text()))
                    #print dir(line)
                    #print line.get_text()
                    #raw_input()
                #text.append(obj.get_text())
            elif isinstance(obj, LTTextLine):
                assert False, 'Expected no lines at top of tree'
            else:
                pass

        yield text

def parse_config(argv):
    parser = argparse.ArgumentParser(description='Converts the input pdf file into a table and outputs to CSV')
    parser.add_argument('--input', '-i',
            required=True,
            type=str,
            help='The pdf file to convert')
    parser.add_argument('--page', '-p',
            type=int,
            default=None,
            help='Specifies a single page to convert')

    return parser.parse_args(args=argv)

if __name__ == '__main__':
    sys.exit(main(sys.argv))

