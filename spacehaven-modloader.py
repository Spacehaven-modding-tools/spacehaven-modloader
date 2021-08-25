#!/usr/bin/env python3

import os
import platform
import subprocess
import threading
import traceback
import winreg
from collections import OrderedDict
from tkinter import *
from tkinter import filedialog, messagebox, ttk, font, scrolledtext
#from steamfiles import acf

import re
import loader.extract
import loader.load
import ui.database
import ui.header
import ui.launcher
import ui.log
import version
from ui.scrolledlistbox import ScrolledListbox

POSSIBLE_SPACEHAVEN_LOCATIONS = [
    # MacOS
    "/Applications/spacehaven.app",
    "/Applications/Games/spacehaven.app",
    "/Applications/Games/Space Haven/spacehaven.app",
    "./spacehaven.app",
    "../spacehaven.app",
    # could add default steam library location here for mac, unless mac installs steam games in the previous locations?

    # Windows
    "../spacehaven/spacehaven.exe",
    "../../spacehaven/spacehaven.exe",
    "../spacehaven.exe",
    "../../spacehaven.exe",
    "C:/Program Files (x86)/Steam/steamapps/common/SpaceHaven/spacehaven.exe",

    # Linux
    "../SpaceHaven/spacehaven",
    "../../SpaceHaven/spacehaven",
    "~/Games/SpaceHaven/spacehaven",
    ".local/share/Steam/steamapps/common/SpaceHaven/spacehaven",
]
DatabaseHandler = ui.database.ModDatabase

#Frame with built in scrollbar. Used for MonConfigFrame
class ScrollableFrame(ttk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        canvas = Canvas(self)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 30), window=self.scrollable_frame, anchor="nw") 

        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

class Window(Frame):
    def __init__(self, master=None):
        Frame.__init__(self, master)
        self.master = master

        self.master.title("Space Haven Mod Loader v{}".format(version.version))
        # self.master.bind('<FocusIn>', self.focus)


        self.headerImage = PhotoImage(data=ui.header.image, width=1680, height=30)
        self.header = Label(self.master, bg='black', image=self.headerImage)
        self.header.pack(fill=X, padx=0, pady=0)

        self.pack(fill=BOTH, expand=1, padx=4, pady=4)

        self.sizegrip = ttk.Sizegrip(master).pack(side=RIGHT)

        # Used later when binding events.
        # This prevents some obscure bugs.
        closure_self:Window = self

        # separator
        #Frame(self, height=1, bg="grey").pack(fill=X, padx=4, pady=8)

        ##########################################################################################
        #### modBrowser - Center container for the mod list, details, and config.             ####
        ##########################################################################################

        modBrowser = self.modBrowser = PanedWindow(self
            , orient=HORIZONTAL
            , relief=GROOVE
            , borderwidth=4
            , sashcursor='sb_h_double_arrow'
            , sashrelief=SOLID  #choices: RAISED, SUNKEN, FLAT, RIDGE, GROOVE, SOLID
            , sashwidth=8
            , sashpad=8 )
        modBrowser.pack(fill=BOTH, expand=1)

        # MOD SELECTION LISTBOX (left pane)
        modList = self.modList = ScrolledListbox(modBrowser, selectmode=SINGLE) # , activestyle=NONE )
        modList.configure(exportselection=False)
        def evt_ModList_ListboxSelect( evt ):
            w = evt.widget
            sel = w.curselection()
            # Handle problem of this event fireing when Listbox loses focus.
            if sel is None or len(sel)==0:
                return
            index = int(w.curselection()[0])
            value = w.get(index)
            closure_self.showCurrentMod(evt)

        modList.bind('<<ListboxSelect>>', evt_ModList_ListboxSelect)
        modBrowser.add(modList)

        # MOD DETAILS CONTAINER (right pane)
        # Ar vertical paned window inside a horizontal paned window.
        modDetailsWindow = self.modDetailsWindow =  PanedWindow(self
            , orient=VERTICAL
            , relief=GROOVE
            , borderwidth=4
            , sashcursor='sb_v_double_arrow'
            , sashrelief=SOLID  #choices: RAISED, SUNKEN, FLAT, RIDGE, GROOVE, SOLID
            , sashwidth=8
            , sashpad=4 )
        modBrowser.add(modDetailsWindow)

        # MOD DETAILS - Title and Description (top subpane)
        modDetailsFrame = Frame(modDetailsWindow)
        modDetailsWindow.add(modDetailsFrame)

        modDetailTopBar = Frame(modDetailsFrame)
        self.modDetailsName = Label(modDetailTopBar, font="TkDefaultFont 14 bold", anchor=NW)
        self.modDetailsName.pack(side=LEFT, padx=4, pady=4)

        self.modEnableDisable = Button(modDetailTopBar, text="Enable", anchor=NE, command=self.toggle_current_mod)
        self.modEnableDisable.pack(side = RIGHT, padx=4, pady=4)
        modDetailTopBar.pack(side=TOP,fill=X,padx=4,pady=4)

        self.modDetailsDescription = scrolledtext.ScrolledText(modDetailsFrame, wrap=WORD)
        self.modDetailsDescription.pack(side=TOP,fill=BOTH, expand=TRUE)

        modDetailsWindow.add(modDetailsFrame,minsize=100)

        # Create Bottom frame placeholder for later.
        # This is populated when a mod is selected in the Listbox.
        self.modConfigFrame = ScrollableFrame(modDetailsWindow) #Y30 used as default - see line 64

        # separator
        #Frame(self, height=1, bg="grey").pack(fill=X, padx=4, pady=8)
        #ttk.Separator(self,orient='horizontal').pack(fill=X, padx=4, pady=8)

        ##########################################################################################
        #### Footer with Buttons                                                              ####
        ##########################################################################################

        # buttons at the bottom
        buttonFrame = Frame(self)#.pack(fill = X, padx = 4, pady = 8)

        # launcher
        self.launchButton_default_text = "LAUNCH!"
        self.launchButton = Button(buttonFrame, text=self.launchButton_default_text, command=self.launch_wrapper, height = 2, font=font.Font(size = 14, weight = "bold") )
        self.launchButton.pack(fill=X, padx=4, pady=4 )

        #Frame(self, height=1, bg="grey").pack(fill=X, padx=4, pady=8)
        self.spacehavenPicker = Frame(buttonFrame)
        self.spacehavenPicker.pack(fill=X, padx=4, pady=4)
        self.spacehavenBrowse = Button(self.spacehavenPicker, text="Find game...", command=self.browseForSpacehaven)
        self.spacehavenBrowse.pack(side = LEFT, padx=8, pady=4)

        #self.spacehavenGameLabel = Label(self, text="Game Location :", anchor=NE)
        #self.spacehavenGameLabel.pack(side = LEFT, padx=4, pady=4)
        # game path
        self.spacehavenText = Entry(self.spacehavenPicker)

        # damn cant align properly with the "find game" button...
        self.spacehavenText.pack(fill = X, padx=4, pady=4, anchor = S)

        self.spacehavenPicker.pack(fill=X, padx=0, pady=0)
        Frame(self, height=1, bg="grey").pack(fill=X, padx=4, pady=8)

        self.quitButton = Button(buttonFrame, text="Quit", command=self.quit)
        self.quitButton.pack(side=RIGHT, expand = False, padx=8, pady=4)
        
        self.annotateButton = Button(buttonFrame, text="Annotate XML", command = lambda: self.start_background_task(self.annotate, "Annotating"))
        self.annotateButton.pack(side=RIGHT, expand = False, padx=8, pady=4)
        
        self.extractButton = Button(buttonFrame, text="Extract game assets", command = lambda: self.start_background_task(self.extract_assets, "Extracting"))
        self.extractButton.pack(side=RIGHT, expand = False, padx=8, pady=4)
        
        self.modListOpenFolder = Button(buttonFrame, text="Open Mods Folder", command=self.openModFolder)
        self.modListOpenFolder.pack(side = RIGHT, expand = False, padx=8, pady=4)

        self.modListRefresh = Button(buttonFrame, text="Refresh Mods", command=self.refreshModList)
        self.modListRefresh.pack(side = RIGHT, expand = False, padx=8, pady=4)
        
        self.quickLaunchClear = Button(buttonFrame, text="Clear Quicklaunch file", command=self.clear_quick_launch)
        self.quickLaunchClear.pack(side = RIGHT, expand = False, padx=8, pady=4)

        buttonFrame.pack(fill = X, padx = 4, pady = 8)

        self.autolocateSpacehaven()

    def autolocateSpacehaven(self):
        self.gamePath = None
        self.jarPath = None
        self.modPath = None

        # Open previous location if known
        try:
            with open("previous_spacehaven_path.txt", 'r') as f:
                location = f.read()
                if os.path.exists(location):
                    self.locateSpacehaven(location)
                    return
        except FileNotFoundError:
            ui.log.log("Unable to get last space haven location. Autolocating again.")

        # Steam based locator (Windows)
        try:
            registry_path:str = "SOFTWARE\\WOW6432Node\\Valve\\Steam" if (platform.architecture()[0] == "64bit") else "SOFTWARE\\Valve\\Steam"
            steam_path:str = winreg.QueryValueEx(winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, registry_path), "InstallPath")[0]
            spacehaven_exe:str = r"\steamapps\common\SpaceHaven\spacehaven.exe"

            ''' DEPRECATED
            library_folders = acf.load(open(steam_path + "\\steamapps\\libraryfolders.vdf"), wrapper=OrderedDict)
            locations = [steam_path + "\\steamapps\\common\\SpaceHaven\\spacehaven.exe"]
            for key, value in library_folders["LibraryFolders"].items():
                if str.isnumeric(key): locations.append(value + "\\steamapps\\common\\SpaceHaven\\spacehaven.exe")
            for location in locations:
                if os.path.exists(location):
                    self.locateSpacehaven(location)
                    return
            '''

            def vdf_path_parse(libfile):
                filestring:str = open(steam_path + r"\steamapps\libraryfolders.vdf").read()
                paths = re.findall(r'\s*\"path\"\s*\"([^\"]*)', filestring)                      
                return paths

            library_folders = vdf_path_parse(open(steam_path + r"\steamapps\libraryfolders.vdf"))
            locations = [steam_path + spacehaven_exe]
            for value in library_folders:
                locations.append( value.replace( "\\\\" , "\\" ) + spacehaven_exe)
            for location in locations:
                if os.path.exists(location):
                    self.locateSpacehaven(location)
                    return

        except FileNotFoundError:
            ui.log.log("Unable to locate Steam registry keys or library paths, aborting Steam autolocator")

        for location in POSSIBLE_SPACEHAVEN_LOCATIONS:
            try: 
                location = os.path.abspath(location)
                if os.path.exists(location):
                    self.locateSpacehaven(location)
                    return
            except:
                pass
        ui.log.log("Unable to autolocate installation. User will need to pick manually.")

    def locateSpacehaven(self, path):
        if path is None:
            return

        if path.endswith('.app'):
            self.gamePath = path
            self.jarPath = path + '/Contents/Resources/spacehaven.jar'
            self.modPath = path + '/Contents/Resources/mods'

        elif path.endswith('.jar'):
            self.gamePath = path
            self.jarPath = path
            self.modPath = os.path.join(os.path.dirname(path), "mods")

        else:
            self.gamePath = path
            self.jarPath = os.path.join(os.path.dirname(path), "spacehaven.jar")
            self.modPath = os.path.join(os.path.dirname(path), "mods")

        if not os.path.exists(self.modPath):
            os.mkdir(self.modPath)

        ui.log.setGameModPath(self.modPath)
        ui.log.log("Discovered game at {}".format(path))
        ui.log.log("  gamePath: {}".format(self.gamePath))
        ui.log.log("  modPath: {}".format(self.modPath))
        ui.log.log("  jarPath: {}".format(self.jarPath))
        
        
        with open("previous_spacehaven_path.txt", 'w') as f:
            f.write(path)
        
        self.checkForLoadedMods()

        self.gameInfo = ui.gameinfo.GameInfo(self.jarPath)

        self.spacehavenText.delete(0, 'end')
        self.spacehavenText.insert(0, self.gamePath)
        
        self.modPath = [self.modPath, ]
        try:
            with open("extra_mods_path.txt", 'r') as f:
                for mod_path in f.read().split('\n'):
                    if mod_path.strip():
                        self.modPath.append(mod_path.strip())
        except:
            pass
        
        DatabaseHandler(self.modPath, self.gameInfo)
        self.refreshModList()

    def checkForLoadedMods(self):
        if self.jarPath is None:
            return

        loader.load.unload(self.jarPath)

    def browseForSpacehaven(self):
        import platform
        
        filetypes = []
        if platform.system() == "Windows":
            filetypes.append(('spacehaven.exe', '*.exe'))
        elif platform.system() == "Darwin":
            filetypes.append(('spacehaven.app', '*.app'))
        elif platform.system() == "Linux":
            filetypes.append(('all files', '*'))
        
        self.locateSpacehaven(
            filedialog.askopenfilename(
                parent=self.master,
                title="Locate spacehaven",
                filetypes=filetypes,
            )
        )
    
    #def focus(self, _arg=None):
    #    # disabled, refreshes too much and resets the selection
    #    # self.refreshModList()
    #    pass

    def refreshModList(self):
        try:
            # might fail at init time
            previously_selected = self.selected_mod()
        except:
            previously_selected = None
            pass
        self.modList.delete(0, END)

        if self.modPath is None:
            self.showModError("Spacehaven not found", "Please use the 'Find game' button below to locate Spacehaven.")
            return

        DatabaseHandler.getInstance().locateMods()
        
        mod_idx = 0
        for mod in DatabaseHandler.getRegisteredMods():
            self.modList.insert(END, mod.name)
            mod.display_idx = mod_idx
            
            self.update_list_style(mod)
            if previously_selected and mod == previously_selected.name:
                self.modList.selection_set(mod_idx)
            mod_idx += 1
        
        self.check_quick_launch()
        self.showCurrentMod()
    
    def update_list_style(self, mod):
        if mod.enabled:
            self.modList.itemconfig(mod.display_idx, foreground = 'black', selectforeground = 'white')
        else:
            self.modList.itemconfig(mod.display_idx, foreground = 'grey', selectforeground = 'lightgrey')
    
    def selected_mod(self):
        if DatabaseHandler.getInstance().isEmpty():
            return None
        if len(self.modList.curselection()) == 0:
            self.modList.selection_set(0)
            selected = 0
        else:
            selected = self.modList.curselection()[0]

        return DatabaseHandler.getRegisteredMods()[selected]
            
    def showCurrentMod(self, _arg=None):
        self.showMod(self.selected_mod())
    
    def toggle_current_mod(self):
        mod = self.selected_mod()
        if not mod:
            return
        
        if mod.enabled:
            mod.disable()
        else:
            mod.enable()
        
        self.update_list_style(mod)
        self.showMod(mod)
        self.check_quick_launch()
    
    def update_description(self, description):
        self.modDetailsDescription.config(state="normal")
        self.modDetailsDescription.delete(1.0, END)
        self.modDetailsDescription.insert(END, description)
        self.modDetailsDescription.config(state="disabled")

    def create_ModConfigVariableEntry(self, configFrame:Frame, mod:ui.database.Mod, var:ui.database.ModConfigVar):
        # TODO: Maybe change this to use grid instead of pack for better presentation?
        valFrame = Frame(configFrame)
        # label for variable description
        Label(valFrame,text=var.desc).pack(side=LEFT)

        # Entry for value 
        tk_value = StringVar(valFrame, value=var.value)
        def _value_update(name, index, mode, mod, var, tk_value):
            var.value = tk_value.get()
        # Checkbox option
        if (var.type == "toggle"):
            c1 = Checkbutton(valFrame,variable=tk_value,onvalue=var.max,offvalue=var.min)
            c1.pack()
        # Else uses entry text
        else:
            entryValue = Entry(valFrame,textvariable=tk_value)
            entryValue.pack(side=RIGHT)

        tk_value.trace('w', lambda name,index,mode : _value_update(name,index,mode,mod,var,tk_value) )


        # Link the UI variable back to the config variable for later.
        var.ui_stringvar = tk_value

        # label for debug information
        #Label(valFrame,text="").pack(side=RIGHT)

        valFrame.pack(fill=X)
        return

    def reset_ModConfigVariables(self):
        mod = self.selected_mod()
        if not mod or not mod.variables:
            return
        for var in mod.variables:
            if (var.type == "toggle"):
                var.ui_stringvar.set(var.default)
            else:
                var.value = var.default
                var.ui_stringvar.set(var.default)
            self.modConfigFrame.update()

    def update_mod_config_ui(self,mod:ui.database.Mod):
        try:
            self.modConfigFrame.destroy()
        except:
            pass
        
        try:
            if len(mod.variables)>0:
                self.modConfigFrame = ScrollableFrame(self.modDetailsWindow)
            else:
                return
        except:
            return

        # Reset button at top.
        resetFrame = Frame(self.modConfigFrame.scrollable_frame)
        resetButton = Button(resetFrame, text="Reset to Defaults", anchor=NE, command=self.reset_ModConfigVariables)
        resetButton.pack(side = RIGHT, padx=4, pady=4)
        resetFrame.pack(fill=X)

        for v in mod.variables:
            self.create_ModConfigVariableEntry( self.modConfigFrame.scrollable_frame, mod, v)

        self.modConfigFrame.update()
        self.modDetailsWindow.add(self.modConfigFrame, minsize=self.modConfigFrame.winfo_reqheight())
        self.modDetailsWindow.update()

    def showMod(self, mod:ui.database.Mod):
        if not mod:
            return self.showModError("No mods found", "Please install some mods into your mods folder.")
        
        title = mod.title()
        if mod.enabled:
            command_label = "Disable"
        else:
            command_label = "Enable"
            title += " [DISABLED]"
        
        self.modDetailsName.config(text = title)
        self.modEnableDisable.config(text = command_label)
        self.update_description(mod.getDescription())
        self.update_mod_config_ui(mod)
    
    def showModError(self, title, error):
        self.modDetailsName.config(text = title)
        self.update_description(error)
        
    def openModFolder(self):
        ui.launcher.open(self.modPath[0])
    
    def set_ui_state(self, state, message):
        self.launchButton.config(state = state, text = message)
        self.modEnableDisable.config(state = state)
        self.spacehavenBrowse.config(state = state)
        self.quickLaunchClear.config(state = state)
        self.modListRefresh.config(state = state)
        self.modListOpenFolder.config(state = state)
        self.extractButton.config(state = state)
        self.annotateButton.config(state = state)
        self.quitButton.config(state = state)
    
    can_quit = True
    def disable_UI(self, message):
        self.set_ui_state(DISABLED, message)
        self.config(cursor = 'wait')
        self.can_quit = False
    
    def enable_UI(self, message):
        self.set_ui_state(NORMAL, message)
        self.config(cursor = '')
        self.can_quit = True
    
    background_refresh_delay = 1000
    background_thread = None
    background_finished = True
    
    def start_background_task(self, task, message):
        self.disable_UI(message)
        
        ui.log.logger.backgroundState = message
        
        self.background_finished = False
        # for counting the iterations in update_background_state
        self.background_counter = 0
        
        def _wrapper():
            try:
                task()
            finally:
                self.background_finished = True
        
        self.background_thread = threading.Thread(target = _wrapper)
        self.background_thread.start()
        self.after(self.background_refresh_delay, self.update_background_state)
        
    def update_background_state(self):
        extra_label = "." * (self.background_counter % 5)
        self.background_counter += 1
        
        self.launchButton.config(text = extra_label + " " + ui.log.logger.backgroundState + " " + extra_label)
        if self.background_finished:
            self.background_thread.join()
            self.background_thread = None
            self.enable_UI(self.launchButton_default_text)
            self.check_quick_launch()
        else:
            self.after(self.background_refresh_delay, self.update_background_state)
    
    def _core_extract_path(self):
        return os.path.join(self.modPath[0], "spacehaven_" + self.gameInfo.version)
    
    def extract_assets(self):
        corePath = self._core_extract_path()
        
        loader.extract.extract(self.jarPath, corePath)
        ui.launcher.open(os.path.join(corePath, 'library'))
    
    def annotate(self):
        corePath = self._core_extract_path()
        ui.log.log(f"Annotating and putting files in {corePath}")
        try:
            loader.assets.annotate.annotate(corePath)
        except Exception as e:
            ui.log.log("  Error during annotation!")
            ui.log.log(repr(e))
        
        ui.launcher.open(os.path.join(corePath, 'library'))
    
    def mods_enabled(self):
        return DatabaseHandler.getActiveMods()
    
    def current_mods_signature(self):
        import hashlib
        
        mods_signature = ["spacehaven", self.gameInfo.version]
        # mods are supposedly ordered alphabetically 
        for mod in self.mods_enabled():
            mods_signature.append(mod.name)
            mods_signature.append(mod.version or "VERSION_UNKNOWN")
        
        text_sig = "__".join(mods_signature).lower()
        md5 = hashlib.md5(text_sig.encode('utf-8')).hexdigest()
        return md5
    
    def quick_launch_available(self):
        mods_sig = self.current_mods_signature()
        return os.path.isfile(loader.load.quick_launch_filename(mods_sig))
    
    def check_quick_launch(self):
        if not self.mods_enabled():
            self.launchButton_default_text = "LAUNCH ORIGINAL GAME"
            self.quickLaunchClear.config(state = DISABLED)
        elif self.quick_launch_available():
            self.launchButton_default_text = "QUICKLAUNCH!"
            self.quickLaunchClear.config(state = NORMAL)
        else:
            self.launchButton_default_text = "LAUNCH!"
            self.quickLaunchClear.config(state = DISABLED)
        self.launchButton.config(text = self.launchButton_default_text)
    
    def clear_quick_launch(self):
        try:
            os.unlink(loader.load.quick_launch_filename(self.current_mods_signature()))
        except:
            pass
        self.check_quick_launch()
    
    def launch_wrapper(self):
        if not self.mods_enabled():
            task = self.launch_vanilla
            message = "Launching original game"
        elif self.quick_launch_available():
            task = self.quick_launch
            message = "Quicklaunching"
        else:
            task = self.patchAndLaunch
            message = "Launching"
        
        self.start_background_task(task, message)
    
    def launch_vanilla(self):
        ui.launcher.launchAndWait(self.gamePath)
    
    def quick_launch(self):
        try:
            loader.load.quickload(self.jarPath, self.current_mods_signature())
            ui.launcher.launchAndWait(self.gamePath)
            # FIXME this will crash if the game restarts by itself (changing language)
            loader.load.unload(self.jarPath)
        except Exception as ex:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error during quick launch", traceback.format_exc(3))
    
    def patchAndLaunch(self):
        #activeModPaths = [mod.path for mod in DatabaseHandler.getActiveMods()]

        activeMods = DatabaseHandler.getActiveMods()

        # If any active mods have variables, save them.
        for mod in activeMods:
            if mod.variables:
                #mod.info_xml.write(mod.info_file)
                mod.saveConfig()

        
        try:
            loader.load.load(self.jarPath, activeMods, self.current_mods_signature())
            ui.launcher.launchAndWait(self.gamePath)
            loader.load.unload(self.jarPath)
        except Exception as ex:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error loading mods", traceback.format_exc(3))
    
    def quit(self):
        if self.can_quit:
            self.master.destroy()
            return
        
        messagebox.showerror("Error", "Cannot quit while a task is running!")


def handleException(type, value, trace):
    message = "".join(traceback.format_exception(type, value, trace))

    ui.log.log("!! Exception !!")
    ui.log.log(message)

    messagebox.showerror("Error", "Sorry, something went wrong!\n\n"
                                  "Please open an issue at https://github.com/anatarist/spacehaven-modloader and attach logs.txt from your mods/ folder.")


if __name__ == "__main__":
    root = Tk()
    root.geometry("890x669")
    root.report_callback_exception = handleException

    # HACK: Button labels don't appear until the window is resized with py2app
    def fixNoButtonLabelsBug():
        root.geometry("890x670")

    root.resizable(True, True)

    app = Window(root)
    root.update()
    root.update_idletasks()
    root.after(0, fixNoButtonLabelsBug)
    root.protocol("WM_DELETE_WINDOW", app.quit)
    root.mainloop()
