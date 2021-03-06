# Copyright 2009-2014 Ram Rachum.
# This program is distributed under the MIT license.


from __future__ import with_statement

import os.path, sys
sys.path += [
    os.path.dirname(__file__), 
    os.path.join(os.path.dirname(__file__), 'third_party.zip'), 
]


import sys
import inspect

import wingapi

import shared

TAB_KEY = 15 if 'linux' in sys.platform else '48' if 'darwin' in sys.platform \
                                                                         else 9


_characters_that_need_shift = ('!@#$%^&*()_+~{}>:"?|<')

def _type_string(string):
    assert shared.autopy_available
    import autopy.key
    for character in string:
        if character in _characters_that_need_shift:
            autopy.key.tap(character, autopy.key.MOD_SHIFT)
        else:
            autopy.key.tap(character)
        autopy.key.tap(135) # F24 for making AHK not interfere
        autopy.key.tap(35) # `End` for making AHK not interfere


def _cute_general_replace(command_name,
                          editor=wingapi.kArgEditor,
                          app=wingapi.kArgApplication):
    assert isinstance(editor, wingapi.CAPIEditor)
    assert isinstance(app, wingapi.CAPIApplication)
    selection_start, selection_end = editor.GetSelection()
    selection = editor.GetDocument().GetCharRange(selection_start,
                                                  selection_end)
    
    if selection:
        wingapi.gApplication.SetClipboard(selection)
        editor.SetSelection(selection_start, selection_start)
        app.ExecuteCommand(command_name)
        if shared.autopy_available:
            import autopy.key
            autopy.key.toggle(autopy.key.K_ALT, False)
            autopy.key.toggle(autopy.key.K_SHIFT, False)
            autopy.key.toggle(autopy.key.K_CONTROL, False)
            autopy.key.toggle(autopy.key.K_META, False)
            #_type_string(selection)
            #autopy.key.tap(autopy.key.K_ESCAPE)
            #autopy.key.toggle(autopy.key.K_ALT, False)
            #autopy.key.tap(TAB_KEY)
            #autopy.key.tap('l', autopy.key.MOD_ALT)
            #autopy.key.tap('v', autopy.key.MOD_CONTROL)
            #autopy.key.tap('a', autopy.key.MOD_CONTROL)
            
        
    else: # not selection
        app.ExecuteCommand(command_name)
        
        
def cute_query_replace(editor=wingapi.kArgEditor,
                       app=wingapi.kArgApplication):
    '''
    Improved version of `query-replace` for finding and replacing in document.
    
    BUGGY: If text is selected, it will be used as the text to search for, and
    the contents of the clipboard will be offered as the replace value.
    
    Implemented on Windows only.
    
    Suggested key combination: `Alt-Comma`
    '''
    return _cute_general_replace('query-replace', editor=editor, app=app)


def cute_replace_string(editor=wingapi.kArgEditor,
                       app=wingapi.kArgApplication):
    '''
    Improved version of `replace-string` for finding and replacing in document.
    
    BUGGY: If text is selected, it will be used as the text to search for, and
    the contents of the clipboard will be offered as the replace value.
    
    Implemented on Windows only.
    
    Suggested key combination: `Alt-Period`
    '''    
    return _cute_general_replace('replace-string', editor=editor, app=app)