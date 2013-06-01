# Copyright 2009-2013 Ram Rachum.
# This program is distributed under the MIT license.

'''
This module defines scripts for selecting invocations and arguments.

See its documentation for more information.
'''

from __future__ import with_statement

import keyword
import itertools
import re
import _ast
import bisect

import os.path, sys; sys.path.append(os.path.dirname(__file__))

import wingapi

import shared

invocation_pattern = re.compile(
    r'''(?<!def )(?<!class )(?<![A-Za-z_0-9])([A-Za-z_][A-Za-z_0-9]*) *\('''
)    
invocation_pattern_for_arguments = re.compile(
    r'''(?<![A-Za-z_0-9])([A-Za-z_][A-Za-z_0-9]*) *\('''
)    
    
def _ast_parse(string):
    return compile(string.replace('\r', ''), '<unknown>', 'exec',
                   _ast.PyCF_ONLY_AST)
    

class ArgumentSearchingFailed(Exception):
    pass
           


def _collect_offsets(call_string, limit_to_keywords=False):
    def _abs_offset(lineno, col_offset):
        current_lineno = 0
        total = 0
        for line in call_string.splitlines():
            current_lineno += 1
            if current_lineno == lineno:
                return col_offset + total
            total += len(line)
    # parse call_string with ast
    #print('f' + call_string)
    try:
        call = _ast_parse('f' + call_string).body[0].value
    except Exception:
        #print('Exception')
        raise ArgumentSearchingFailed
    if not isinstance(call, _ast.Call):
        #print('Not a call')
        raise ArgumentSearchingFailed

    # collect offsets provided by ast
    offsets = []
    for arg in call.args:
        a = arg
        while isinstance(a, _ast.BinOp):
            a = a.left
        offsets.append(_abs_offset(a.lineno, a.col_offset))
    for kw in call.keywords:
        offsets.append(_abs_offset(kw.value.lineno, kw.value.col_offset))
    if call.starargs:
        offsets.append(_abs_offset(call.starargs.lineno,
                                   call.starargs.col_offset))
    if call.kwargs:
        offsets.append(_abs_offset(call.kwargs.lineno,
                                   call.kwargs.col_offset))
    offsets.append(len(call_string))
    return offsets

@shared.lru_cache(maxsize=1000)
def _argpos(call_string, document_offset, limit_to_keywords=False):
    #print(call_string)
    def _find_start(prev_end, offset):
        s = call_string[prev_end:offset]
        #print(repr(s))
        m = re.search('(\(|,)(\s*)((.|\s)*?)$', s)
        return prev_end + m.regs[3][0]
    def _find_end(start, next_offset):
        s = call_string[start:next_offset]
        m = re.search('(\s*)$', s[:max(s.rfind(','), s.rfind(')'))])
        return start + m.start()

    try:
        offsets = _collect_offsets(call_string,
                                   limit_to_keywords=limit_to_keywords)
    except ArgumentSearchingFailed:
        return ()

    result = []
    # previous end
    end = 0
    # given offsets = [9, 14, 21, ...],
    # zip(offsets, offsets[1:]) returns [(9, 14), (14, 21), ...]
    for offset, next_offset in zip(offsets, offsets[1:]):
        #print 'I:', offset, next_offset
        try:
            start = _find_start(end, offset)
            end = _find_end(start, next_offset)
        except AttributeError:
            continue
        #print 'R:', start, end
        if limit_to_keywords:
            candidate = call_string[start:end]
            if not re.match(r'''^ *[A-Za-z_][A-Za-z_0-9]* *=''', candidate):
                continue
        result.append((start, end))
    final_result = tuple((start + document_offset, end + document_offset)
                         for (start, end) in result)
    #print(final_result)
    return final_result

def get_span_of_opening_parenthesis(document, position):
    assert isinstance(document, wingapi.CAPIDocument)
    document_text = shared.get_text(document)
    if not document_text[position] == '(': raise Exception
    for i in range(1, len(document_text) - position):
        portion = document_text[position:position+i+1]
        if portion.count('(') == portion.count(')'):
            if not portion[-1] == ')': raise Exception
            return (position, position + i + 1)
    else:
        return (position, position)
        
    

def _get_matches(document):
    assert isinstance(document, wingapi.CAPIDocument)
    document_text = shared.get_text(document)
    return tuple(match for match in invocation_pattern.finditer(document_text)
                 if not keyword.iskeyword(match.groups()[0]))

def _get_matches_for_arguments(document):
    assert isinstance(document, wingapi.CAPIDocument)
    document_text = shared.get_text(document)
    return tuple(match for match in
                 invocation_pattern_for_arguments.finditer(document_text)
                 if not keyword.iskeyword(match.groups()[0]))

def get_invocation_positions(document):
    matches = _get_matches(document)
    return tuple(match.span(1) for match in matches)
    
def get_argument_batch_positions(document):
    matches = _get_matches_for_arguments(document)
    parenthesis_starts = tuple(match.span(0)[1]-1 for match in matches)
    return map(
        lambda parenthesis_start:
                  get_span_of_opening_parenthesis(document, parenthesis_start),
        parenthesis_starts
    )
    
def get_argument_positions(document, limit_to_keywords=False):
    argument_batch_positions = get_argument_batch_positions(document)
    document_text = shared.get_text(document)
    raw_argument_positions = tuple(itertools.chain(
        *(_argpos(
            document_text[argument_batch_position[0]:
                                                   argument_batch_position[1]],
            document_offset=argument_batch_position[0],
            limit_to_keywords=limit_to_keywords
        )
                       for argument_batch_position in argument_batch_positions)
    ))
    argument_positions = map(
        lambda (start, end):
            shared.strip_segment_from_whitespace_and_newlines(document_text,
                                                              start, end),
        raw_argument_positions
    )
    return argument_positions

###############################################################################


def select_next_invocation(editor=wingapi.kArgEditor,
                           app=wingapi.kArgApplication):
    '''
    Select the next invocation of a callable, e.g `foo.bar(baz)`.
    
    Suggested key combination: `Ctrl-Alt-8`
    '''
    assert isinstance(editor, wingapi.CAPIEditor)
    _, position = editor.GetSelection()
    position += 1

    invocation_positions = get_invocation_positions(editor.GetDocument())
    invocation_ends = tuple(invocation_position[1] for invocation_position in
                            invocation_positions)
    invocation_index = bisect.bisect_left(invocation_ends, position)
    
    if 0 <= invocation_index < len(invocation_ends):
        app.ExecuteCommand('set-visit-history-anchor')
        editor.SetSelection(*invocation_positions[invocation_index])
        

def select_prev_invocation(editor=wingapi.kArgEditor,
                           app=wingapi.kArgApplication):
    '''
    Select the previous invocation of a callable, e.g `foo.bar(baz)`.
    
    Suggested key combination: `Ctrl-Alt-Asterisk`
    '''    
    assert isinstance(editor, wingapi.CAPIEditor)
    position, _ = editor.GetSelection()
    position -= 1

    invocation_positions = get_invocation_positions(editor.GetDocument())
    invocation_starts = tuple(invocation_position[0] for invocation_position
                              in invocation_positions)
    invocation_index = bisect.bisect_left(invocation_starts, position) - 1
    
    if 0 <= invocation_index < len(invocation_starts):
        app.ExecuteCommand('set-visit-history-anchor')
        editor.SetSelection(*invocation_positions[invocation_index])


###############################################################################

def select_next_argument(editor=wingapi.kArgEditor,
                         app=wingapi.kArgApplication,
                         limit_to_keywords=False):
    '''
    Select the next argument to a callable.
    
    Set `limit_to_keywords=True` to go only to a keyword argument.
    
    Suggested key combinations: `Ctrl-R`
                                `Ctrl-Alt-R` for `limit_to_keywords=True`
    '''
    
    assert isinstance(editor, wingapi.CAPIEditor)
    _, position = editor.GetSelection()
    position += 1

    argument_positions = get_argument_positions(
        editor.GetDocument(),
        limit_to_keywords=limit_to_keywords
    )
    #print(argument_positions)
    argument_positions = sorted(argument_positions,
                                key=(lambda (start, end): end))
    argument_ends = tuple(argument_position[1] for argument_position in
                          argument_positions)
    argument_index = bisect.bisect_left(argument_ends, position)
    
    if 0 <= argument_index < len(argument_ends):
        app.ExecuteCommand('set-visit-history-anchor')
        editor.SetSelection(*argument_positions[argument_index])
        

def select_prev_argument(editor=wingapi.kArgEditor,
                         app=wingapi.kArgApplication,
                         limit_to_keywords=False):
    '''
    Select the previous argument to a callable.
    
    Set `limit_to_keywords=True` to go only to a keyword argument.
    
    Suggested key combinations: `Ctrl-Shift-R`
                                `Ctrl-Shift-Alt-R` for `limit_to_keywords=True`
    '''    
    assert isinstance(editor, wingapi.CAPIEditor)
    position, _ = editor.GetSelection()
    position -= 1

    argument_positions = get_argument_positions(
        editor.GetDocument(),
        limit_to_keywords=limit_to_keywords
    )
    #print(argument_positions)
    argument_positions = sorted(argument_positions,
                                key=(lambda (start, end): start))
    argument_ends = tuple(argument_position[0] for argument_position in
                          argument_positions)
    argument_index = bisect.bisect_left(argument_ends, position) - 1
    
    if 0 <= argument_index < len(argument_ends):
        app.ExecuteCommand('set-visit-history-anchor')
        editor.SetSelection(*argument_positions[argument_index])
        