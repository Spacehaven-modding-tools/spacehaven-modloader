"""ScrolledListbox widget adapted from ScrolledText.

See original ScrolledText at:
https://github.com/python/cpython/blob/3.9/Lib/tkinter/scrolledtext.py

Configuration options are passed to the Listbox widget.
A Frame widget is inserted between the master and the text, to hold
the Scrollbar widget.
Most methods calls are inherited from the Text widget; Pack, Grid and
Place methods are redirected to the Frame widget however.
"""

from tkinter import Frame, Listbox, Scrollbar, Pack, Grid, Place
from tkinter.constants import RIGHT, LEFT, Y, BOTH

__all__ = ['ScrolledListbox']

class ScrolledListbox(Listbox):
    def __init__(self, master=None, **kwargs):
        self.frame = Frame(master)
        self.vbar = Scrollbar(self.frame)
        self.vbar.pack(side=RIGHT, fill=Y)

        kwargs.update({'yscrollcommand': self.vbar.set})
        self.list = Listbox.__init__(self, self.frame, **kwargs)
        self.pack(side=LEFT, fill=BOTH, expand=True)
        self.vbar['command'] = self.yview

        # Copy geometry methods of self.frame without overriding Listbox
        # methods -- hack!
        listbox_meths = vars(Listbox).keys()
        methods = vars(Pack).keys() | vars(Grid).keys() | vars(Place).keys()
        methods = methods.difference(listbox_meths)

        for m in methods:
            if m[0] != '_' and m != 'config' and m != 'configure':
                setattr(self, m, getattr(self.frame, m))

    def __str__(self):
        return str(self.frame)


def example():
    from tkinter.constants import END

    slist = ScrolledListbox(bg='white', height=3)
    slist.insert(1, "Alpha")
    slist.insert(2, "Bravo")
    slist.insert(3, "Charlie")
    slist.insert(4, "Delta")
    slist.insert(5, "Echo")    
    slist.insert(6, "Foxtrot")    
    slist.pack(fill=BOTH, side=LEFT, expand=True)
    slist.focus_set()
    slist.mainloop()


if __name__ == "__main__":
    example()
