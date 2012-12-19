#!/usr/bin/python2.7

import sys
import os
import argparse
import itertools
import re
import math
import collections
import bisect

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
            breakdown = PageBreakdown(page)
            print breakdown.location
            breakdown.clean_table()
            continue
            for e in sorted(breakdown.table):
                colid, rem = divmod(e[0][0][0], 5)

                print divmod(e[0][0][0], 5)
                print e[0]
                print e[1].strip()

    return 0

def find_lt(val, iterable, mapping=None):
    if mapping:
        iterable = map(mapping, iterable)
    return len(iterable)-1-bisect.bisect_left(list(reversed(iterable)), val)


class PageBreakdown(object):
    def __init__(self, page):
        super(PageBreakdown, self).__init__()

        self.raw = page

        org_page = PageBreakdown._org_page(page)
        assert len(org_page['LOCATION']) == 1

        self.location = org_page['LOCATION'][0].get_text().strip()
        self.table = org_page['TABLE']

    def clean_table(self):

        #self.table = sorted(self.table, key=lambda x: (x.x0, -x.y0))
        row_indices = filter(lambda x: x.x1<40, self.table)
        row_dividers = map(lambda x: x.y0+5, row_indices)

        item_row_indices = [ find_lt(val.y0, row_dividers) for val in self.table ]

        rows = collections.defaultdict(list)
        for k, v in zip(item_row_indices, self.table):
            rows[k].append(v)

        rows = dict( [ (k, sorted(v, key=lambda x:(x.x0, -x.y0))) for k,v in rows.items() ] )
        for k,v in sorted(rows.items()):
            for i in v:
                sys.stdout.write('{} ({}), '.format(i.get_text().strip(), int(i.x0)))
            for i in v[1:]
            print

        return

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

    return parser.parse_args(args=argv)

if __name__ == '__main__':
    sys.exit(main(sys.argv))

