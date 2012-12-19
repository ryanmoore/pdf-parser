#!/usr/bin/python2.7

import sys
import os
import argparse
import itertools
import re
import math
import collections
import bisect
import time
import datetime

COLUMN_PADDING = 30

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

import csv

def main(argv):

    config = parse_config(argv[1:])

    start = time.time()
    with open(config.input, 'rb') as infile:
        with open(config.output, 'wb') as outfile:
            writer = csv.writer(outfile)

            parser = PDFParser(infile)
            doc    = PDFDocument()
            parser.set_document(doc)
            doc.set_parser(parser)
            doc.initialize()

            assert doc.is_extractable

            template_page = create_breakdown(next(itertools.islice(doc.get_pages(), config.template, config.template+1)), None)
            template_page.clean_table()

            print 'Doing pages ( {}, {} )'.format(config.start, config.end)
            pages = itertools.islice(doc.get_pages(), config.start-1, config.end-1)

            for i,page in enumerate(pages):
                breakdown = create_breakdown(page, template_page.col_dividers)
                print('{} ( {} / {} ) {}'.format(str(datetime.timedelta(seconds=int(time.time()-start))), i+1, config.end-config.start, breakdown.location))
                breakdown.write_table(writer)
    print 'Elapsed:', str(datetime.timedelta(seconds=int(time.time()-start)))
    return 0

def create_breakdown(page, col_dividers):
    rsrcmanager = PDFResourceManager()
    laparams = LAParams()
    device = PDFPageAggregator(rsrcmanager, laparams=laparams)
    interpreter = PDFPageInterpreter(rsrcmanager, device)

    interpreter.process_page(page)
    layout = device.get_result()

    text = []
    for obj in layout:
        if isinstance(obj, LTTextBox):
            for line in obj:
                text.append(line)
        elif isinstance(obj, LTTextLine):
            assert False, 'Expected no lines at top of tree'
        else:
            pass

    return PageBreakdown(text, col_dividers)


def find_lt(val, iterable, mapping=None):
    if mapping:
        iterable = map(mapping, iterable)
    return len(iterable)-1-bisect.bisect_left(list(reversed(iterable)), val)


class PageBreakdown(object):
    def __init__(self, page, col_dividers=None):
        super(PageBreakdown, self).__init__()

        self.raw = page

        org_page = PageBreakdown._org_page(page)
        assert len(org_page['LOCATION']) == 1

        self.location = org_page['LOCATION'][0].get_text().strip()
        self.table = org_page['TABLE']
        self.cleaned = False
        self.col_dividers = col_dividers

    def pprint_table(self):
        for row in self.table:
            for elt in row:
                try:
                    sys.stdout.write('{}, '.format(elt.get_text().strip()))
                except:
                    sys.stdout.write('{}, '.format(elt))
            sys.stdout.write('\n'+'-'*20+'\n')

    def write_table(self, outcsv):
        self.clean_table()
        outcsv.writerows(self.table)

    def clean_table(self):
        if self.cleaned:
            return
        self.cleaned = True

        self.table = [ x for x in self.table if len(x.get_text().strip()) ]

        #self.table = sorted(self.table, key=lambda x: (x.x0, -x.y0))
        row_indices = filter(lambda x: x.x1<40, self.table)
        row_dividers = map(lambda x: x.y0+5, row_indices)

        item_row_indices = [ find_lt(val.y0, row_dividers) for val in self.table ]

        rows = collections.defaultdict(list)
        for k, v in zip(item_row_indices, self.table):
            rows[k].append(v)

        #only take the values, but order them by their key
        rows = zip(*sorted(rows.items()))[1]

        #sort each row by x0
        rows = [ sorted(r, key=lambda x:(x.x0, -x.y0)) for r in rows ]

        #first column is easy, all rows have an index
        self.table = [ [ self.location, r[0].get_text().strip() ] for r in rows ]
        #first column done, remove it
        rows = [ r[1:] for r in rows ]


        if self.col_dividers is None:
            col_xvalues = sorted( map(lambda x: x.x0, list( itertools.chain.from_iterable(rows) ) ) )
            self.col_dividers = []
            for v in col_xvalues:
                if all( abs(x-v)>COLUMN_PADDING for x in self.col_dividers):
                    self.col_dividers.append(int(v))

            print self.col_dividers

        #fill out table with empty values for all columns except first (already completed)
        self.table = [ row+[ '' for c in self.col_dividers ] for row in self.table ]

        #populate table
        for row_index,r in enumerate(rows):
            for elt in r:
                index = bisect.bisect_left( self.col_dividers, elt.x0 ) + 1
                #if the string is nonempty, separate with backslash
                if self.table[row_index][index]:
                    div_symbol = '\\'
                else:
                    div_symbol = ''
                self.table[row_index][index] += div_symbol+elt.get_text().strip()

            #all should have populated final column
            assert self.table[row_index][-1] is not None

    @staticmethod
    def _org_page(page):
        #sort
        top_to_bott = sorted(page, key=lambda x: (-1.0*x.y0, x.x0))

        stages = ['HEADERS', 'LOCATION', 'TABLE']
        stage = -1

        org_page = {}

        #last item on page should be a page number
        assert re.search('-\s*\d+\s*-', top_to_bott[-1].get_text())

        #crop page number from our consideration
        top_to_bott = top_to_bott[:-1]

        for line in top_to_bott:
            if is_boundary(line):
                stage += 1
                org_page[stages[stage]] = []
                #print '='*40+'\n'+stages[stage]+'\n'+'='*40
            else:
                assert stage in range(len(stages))
                org_page[stages[stage]].append(line)

                #print coord, line
                #sys.exit(1)

        return org_page

def is_boundary(line):
    return '*****' in line.get_text()

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
        for obj in layout:
            if isinstance(obj, LTTextBox):
                for line in obj:
                    #coord = ((line.x0, line.y0), (line.x1, line.y1))
                    text.append(line)
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
    parser.add_argument('--output', '-o',
            type=str,
            required=True,
            help='Specifies the destination file')
    parser.add_argument('--template', '-t',
            type=int,
            required=True,
            help='The index of a page which should be used to generate column divisions')
    parser.add_argument('--start', '-s',
            type=int,
            required=True,
            help='The index giving which page to start the processing.')
    parser.add_argument('--end', '-e',
            type=int,
            default=None,
            help='The index giving which page to stop the processing. None is end.')

    return parser.parse_args(args=argv)

if __name__ == '__main__':
    sys.exit(main(sys.argv))

