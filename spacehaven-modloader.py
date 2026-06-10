#!/usr/bin/env python3

import os
import platform
import threading
import traceback
import vdf
from pathlib import Path
from tkinter import *
from tkinter import filedialog, messagebox, ttk, font, scrolledtext

# from steamfiles import acf

import loader.extract
import loader.load
import ui.database
from loader.assets.annotate import annotate
from ui.gameinfo import GameInfo
import ui.header
import ui.launcher
import ui.log
import ui.paths
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


def _read_text_file(path):
    with open(path, "r", encoding="utf-8") as inFile:
        return inFile.read()


def _write_text_file(path, value):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as outFile:
        outFile.write(value)
    os.replace(tmp_path, path)


# Frame with built in scrollbar. Used for MonConfigFrame
class ScrollableFrame(ttk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        canvas = Canvas(self)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        self._mousewheel_bound = False
        self._scrollregion_after_id = None
        self._resize_after_id = None
        self._last_canvas_width = None

        def _update_scrollregion():
            self._scrollregion_after_id = None
            try:
                if canvas.winfo_exists():
                    canvas.configure(scrollregion=canvas.bbox("all"))
            except TclError:
                return

        def _schedule_scrollregion(_event=None):
            if self._scrollregion_after_id:
                try:
                    self.after_cancel(self._scrollregion_after_id)
                except TclError:
                    pass
            self._scrollregion_after_id = self.after(40, _update_scrollregion)

        self.scrollable_frame.bind("<Configure>", _schedule_scrollregion)

        window_id = canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        def _resize_scrollable_frame(width):
            self._resize_after_id = None
            if self._last_canvas_width == width:
                return
            self._last_canvas_width = width
            try:
                if canvas.winfo_exists():
                    canvas.itemconfigure(window_id, width=width)
            except TclError:
                return

        def _schedule_resize_scrollable_frame(event):
            width = event.width
            if self._resize_after_id:
                try:
                    self.after_cancel(self._resize_after_id)
                except TclError:
                    pass
            self._resize_after_id = self.after(40, lambda: _resize_scrollable_frame(width))

        canvas.bind("<Configure>", _schedule_resize_scrollable_frame)

        def _on_mousewheel(event):
            try:
                if not canvas.winfo_exists():
                    return "break"
                if event.num == 4:
                    canvas.yview_scroll(-1, "units")
                elif event.num == 5:
                    canvas.yview_scroll(1, "units")
                else:
                    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except TclError:
                return "break"
            return "break"

        def _bind_mousewheel(_event=None):
            if self._mousewheel_bound:
                return
            canvas.bind_all("<MouseWheel>", _on_mousewheel, add="+")
            canvas.bind_all("<Button-4>", _on_mousewheel, add="+")
            canvas.bind_all("<Button-5>", _on_mousewheel, add="+")
            self._mousewheel_bound = True

        def _unbind_mousewheel(_event=None):
            if not self._mousewheel_bound:
                return
            # bind_all/unbind_all clear every binding; only do it when this
            # frame is the one currently owning the mousewheel.
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")
            self._mousewheel_bound = False

        def _cancel_pending_callbacks(_event=None):
            _unbind_mousewheel()
            for after_id in [self._scrollregion_after_id, self._resize_after_id]:
                if after_id:
                    try:
                        self.after_cancel(after_id)
                    except TclError:
                        pass
            self._scrollregion_after_id = None
            self._resize_after_id = None

        canvas.bind("<Enter>", _bind_mousewheel)
        self.scrollable_frame.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)
        self.scrollable_frame.bind("<Leave>", _unbind_mousewheel)
        self.bind("<Destroy>", _cancel_pending_callbacks)

        canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas = canvas

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")


class Window(Frame):
    def __init__(self, master=None):
        Frame.__init__(self, master)
        self.master = master

        self.master.title("Space Haven Mod Loader v{}".format(version.version))
        # self.master.bind('<FocusIn>', self.focus)

        self.headerImage = PhotoImage(data=ui.header.image, width=1680, height=30)
        self.header = Label(self.master, bg="black", image=self.headerImage)
        self.header.pack(fill=X, padx=0, pady=0)

        self.pack(fill=BOTH, expand=1, padx=4, pady=4)

        self.sizegrip = ttk.Sizegrip(master).pack(side=RIGHT)

        # Used later when binding events.
        # This prevents some obscure bugs.
        closure_self: Window = self
        self._mod_list_suppress = False
        self.current_config_mod = None
        self.config_dirty = False
        self.config_filter_var = StringVar()
        self.config_status_var = StringVar(value="No unsaved changes")

        # separator
        # Frame(self, height=1, bg="grey").pack(fill=X, padx=4, pady=8)

        ##########################################################################################
        #### modBrowser - Center container for the mod list, details, and config.             ####
        ##########################################################################################

        modBrowser = self.modBrowser = PanedWindow(
            self, orient=HORIZONTAL, relief=GROOVE, borderwidth=4, sashcursor="sb_h_double_arrow", sashrelief=SOLID, sashwidth=8, sashpad=8  # choices: RAISED, SUNKEN, FLAT, RIDGE, GROOVE, SOLID
        )
        modBrowser.pack(fill=BOTH, expand=1)

        # MOD SELECTION LISTBOX (left pane)
        modList = self.modList = ScrolledListbox(modBrowser, selectmode=SINGLE)  # , activestyle=NONE )
        modList.configure(exportselection=False)

        def evt_ModList_ListboxSelect(evt):
            w = evt.widget
            sel = w.curselection()
            # Handle problem of this event fireing when Listbox loses focus.
            if sel is None or len(sel) == 0:
                return
            if closure_self._mod_list_suppress:
                return
            index = int(w.curselection()[0])
            closure_self.show_mod_at_index(index)

        modList.bind("<<ListboxSelect>>", evt_ModList_ListboxSelect)
        modBrowser.add(modList)

        # MOD DETAILS CONTAINER (right pane)
        # Ar vertical paned window inside a horizontal paned window.
        modDetailsWindow = self.modDetailsWindow = PanedWindow(
            self, orient=VERTICAL, relief=GROOVE, borderwidth=4, sashcursor="sb_v_double_arrow", sashrelief=SOLID, sashwidth=8, sashpad=4  # choices: RAISED, SUNKEN, FLAT, RIDGE, GROOVE, SOLID
        )
        modBrowser.add(modDetailsWindow)

        # MOD DETAILS - Title and Description (top subpane)
        modDetailsFrame = Frame(modDetailsWindow)
        modDetailsWindow.add(modDetailsFrame)

        modDetailTopBar = Frame(modDetailsFrame)
        self.modDetailsName = Label(modDetailTopBar, font="TkDefaultFont 14 bold", anchor=NW)
        self.modDetailsName.pack(side=LEFT, padx=4, pady=4)

        self.modEnableDisable = Button(modDetailTopBar, text="Enable", anchor=NE, command=self.toggle_current_mod)
        self.modEnableDisable.pack(side=RIGHT, padx=4, pady=4)
        modDetailTopBar.pack(side=TOP, fill=X, padx=4, pady=4)

        self.modDetailsDescription = scrolledtext.ScrolledText(modDetailsFrame, wrap=WORD)
        self.modDetailsDescription.pack(side=TOP, fill=BOTH, expand=TRUE)

        modDetailsWindow.add(modDetailsFrame, minsize=100)

        # Create Bottom frame placeholder for later.
        # This is populated when a mod is selected in the Listbox.
        self.modConfigFrame = ScrollableFrame(modDetailsWindow)  # Y30 used as default - see line 64

        # separator
        # Frame(self, height=1, bg="grey").pack(fill=X, padx=4, pady=8)
        # ttk.Separator(self,orient='horizontal').pack(fill=X, padx=4, pady=8)

        ##########################################################################################
        #### Footer with Buttons                                                              ####
        ##########################################################################################

        # buttons at the bottom
        buttonFrame = Frame(self)  # .pack(fill = X, padx = 4, pady = 8)

        # launcher
        self.launchButton_default_text = "LAUNCH!"
        self.launchButton = Button(buttonFrame, text=self.launchButton_default_text, command=self.launch_wrapper, height=2, font=font.Font(size=14, weight="bold"))
        self.launchButton.pack(side=LEFT, padx=8, pady=4)

        # Frame(self, height=1, bg="grey").pack(fill=X, padx=4, pady=8)
        self.spacehavenPicker = Frame(buttonFrame)
        self.spacehavenPicker.pack(fill=X, padx=4, pady=4)
        self.spacehavenBrowse = Button(self.spacehavenPicker, text="Find game...", command=self.browseForSpacehaven)
        self.spacehavenBrowse.pack(side=LEFT, padx=8, pady=4)

        # self.spacehavenGameLabel = Label(self, text="Game Location :", anchor=NE)
        # self.spacehavenGameLabel.pack(side = LEFT, padx=4, pady=4)
        # game path
        self.spacehavenText = Entry(self.spacehavenPicker)

        # damn cant align properly with the "find game" button...
        self.spacehavenText.pack(fill=X, padx=4, pady=4, anchor=S)

        self.spacehavenPicker.pack(fill=X, padx=0, pady=0)
        Frame(self, height=1, bg="grey").pack(fill=X, padx=4, pady=8)

        self.quitButton = Button(buttonFrame, text="Quit", command=self.quit)
        self.quitButton.pack(side=RIGHT, expand=False, padx=8, pady=4)

        self.annotateButton = Button(buttonFrame, text="Annotate XML", command=lambda: self.start_background_task(self.annotate, "Annotating"))
        self.annotateButton.pack(side=RIGHT, expand=False, padx=8, pady=4)

        self.extractButton = Button(buttonFrame, text="Extract game assets", command=lambda: self.start_background_task(self.extract_assets, "Extracting"))
        self.extractButton.pack(side=RIGHT, expand=False, padx=8, pady=4)

        self.modListOpenFolder = Button(buttonFrame, text="Open Mods Folder", command=self.openModFolder)
        self.modListOpenFolder.pack(side=RIGHT, expand=False, padx=8, pady=4)

        self.modListRefresh = Button(buttonFrame, text="Refresh Mods", command=self.refreshModList)
        self.modListRefresh.pack(side=RIGHT, expand=False, padx=8, pady=4)

        self.modMoveDown = Button(buttonFrame, text="Move down", command=lambda: self.move_current_mod(1))
        self.modMoveDown.pack(side=RIGHT, expand=False, padx=8, pady=4)

        self.modMoveUp = Button(buttonFrame, text="Move up", command=lambda: self.move_current_mod(-1))
        self.modMoveUp.pack(side=RIGHT, expand=False, padx=8, pady=4)

        self.quickLaunchClear = Button(buttonFrame, text="Clear QuickLaunch cache", command=self.clear_quick_launch)
        self.quickLaunchClear.pack(side=RIGHT, expand=False, padx=8, pady=4)

        buttonFrame.pack(fill=X, padx=4, pady=8)

        self.autolocateSpacehaven()

    def autolocateSpacehaven(self):
        self.gamePath = None
        self.workshopPath: str = None
        self.jarPath = None
        self.modPath = None

        # Read the last known Space Haven location stored next to the executable.
        # This file lives outside the game folder on purpose: we need to find
        # the game before we know which game folder to look inside.
        try:
            location = _read_text_file(loader.load.PREVIOUS_GAME_PATH_FILENAME)
            if os.path.exists(location):
                self.locateSpacehaven(location)
                return
        except FileNotFoundError:
            ui.log.log("Unable to get last space haven location. Autolocating again.")
        except Exception as ex:
            ui.log.log("Unable to read previous Space Haven location: {}".format(ex))

        # Find steam install location automagically
        try:
            steam_path = ""
            game_executable = "spacehaven"
            if platform.system() == "Windows":
                # ONLY import winreg IF we are doing windows
                import winreg

                registry_path = "SOFTWARE\\WOW6432Node\\Valve\\Steam" if (platform.architecture()[0] == "64bit") else "SOFTWARE\\Valve\\Steam"
                steam_path = winreg.QueryValueEx(winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, registry_path), "InstallPath")[0]
                game_executable += ".exe"
            if platform.system() == "Linux":
                steam_path = Path(Path.home(), ".steam", "steam")
            if platform.system() == "Darwin":
                steam_path = Path(Path.home(), "Library", "Application Support", "Steam")
                game_executable += ".app"

            libraryfolders_vdf = vdf.parse(open(str(Path(steam_path, "steamapps", "libraryfolders.vdf"))))["libraryfolders"]
            for key in libraryfolders_vdf:
                value = libraryfolders_vdf[key]
                ui.log.log(str(value))
                # let's see if the game is on the dir
                if not value["apps"].get("979110"):
                    continue

                self.locateSpacehaven(str(Path(value["path"], "steamapps", "common", "SpaceHaven", game_executable)))
                return

        except FileNotFoundError:
            ui.log.log("Unable to locate Steam registry keys or library paths, aborting Steam autolocator")
        except Exception as ex:
            ui.log.log("Unable to use Steam autolocator: {}".format(ex))

        # Brute force method
        for location in POSSIBLE_SPACEHAVEN_LOCATIONS:
            try:
                location = os.path.abspath(location)
                if os.path.exists(location):
                    self.locateSpacehaven(location)
                    return
            except Exception as ex:
                ui.log.log("Unable to check possible Space Haven location {}: {}".format(location, ex))
        ui.log.log("Unable to autolocate installation. User will need to pick manually.")

    def locateSpacehaven(self, path):
        if path is None:
            return

        if path.endswith(".app"):
            self.gamePath = path
            self.jarPath = path + "/Contents/Resources/spacehaven.jar"
            self.modPath = path + "/Contents/Resources/mods"

        elif path.endswith(".jar"):
            self.gamePath = path
            self.jarPath = path
            self.modPath = os.path.join(os.path.dirname(path), "mods")

        else:
            self.gamePath = path
            self.jarPath = os.path.join(os.path.dirname(path), "spacehaven.jar")
            self.modPath = os.path.join(os.path.dirname(path), "mods")

        workshop_path = ui.paths.resolve_workshop_path(self.gamePath)
        self.workshopPath = workshop_path

        if not os.path.exists(self.modPath):
            os.mkdir(self.modPath)

        ui.log.setGameModPath(self.modPath)
        ui.log.log("Discovered game at {}".format(path))
        ui.log.log("  gamePath: {}".format(self.gamePath))
        ui.log.log("  modPath: {}".format(self.modPath))
        ui.log.log("  jarPath: {}".format(self.jarPath))
        if workshop_path:
            ui.log.log("  workshopPath: {}".format(self.workshopPath))
        else:
            ui.log.log("  workshopPath: not available")

        self.save_previous_spacehaven_path(path)

        self.checkForLoadedMods()

        self.gameInfo = GameInfo(self.jarPath)

        self.spacehavenText.delete(0, "end")
        self.spacehavenText.insert(0, self.gamePath)

        self.modPath = [
            self.modPath
        ]

        if workshop_path:
            self.modPath.append(self.workshopPath)

        self.load_extra_mod_paths()

        DatabaseHandler(self.modPath, self.gameInfo)
        self.refreshModList()

    def modloader_state_file(self, filename):
        return loader.load.modloader_state_file(self.jarPath, filename)

    def save_previous_spacehaven_path(self, path):
        # Stored next to the executable so we can read it before knowing where
        # Space Haven lives. Moving this file into <SpaceHaven>/mods/modloader
        # would break the bootstrap on the next launch.
        targetPath = loader.load.PREVIOUS_GAME_PATH_FILENAME
        try:
            _write_text_file(targetPath, path)
            ui.log.log("Saved previous Space Haven path to {}".format(os.path.abspath(targetPath)))
        except Exception as ex:
            ui.log.log("Unable to save previous Space Haven path to {}: {}".format(os.path.abspath(targetPath), ex))

    def load_extra_mod_paths(self):
        statePath = self.modloader_state_file(loader.load.EXTRA_MODS_PATH_FILENAME)
        candidates = [statePath, loader.load.EXTRA_MODS_PATH_FILENAME]
        seen = set()

        for path in candidates:
            if path in seen:
                continue
            seen.add(path)
            try:
                extraPaths = _read_text_file(path)
            except FileNotFoundError:
                continue
            except Exception as ex:
                ui.log.log("Unable to read extra mod paths from {}: {}".format(path, ex))
                continue

            for mod_path in extraPaths.split("\n"):
                mod_path = mod_path.strip()
                if mod_path:
                    self.modPath.append(mod_path)

            if path == loader.load.EXTRA_MODS_PATH_FILENAME:
                self.migrate_extra_mod_paths(path, statePath, extraPaths)
            break

    def migrate_extra_mod_paths(self, legacyPath, statePath, extraPaths):
        try:
            _write_text_file(statePath, extraPaths)
            os.unlink(legacyPath)
            ui.log.log("Migrated extra mod paths to {}".format(statePath))
        except Exception as ex:
            ui.log.log("Unable to migrate extra mod paths to {}: {}".format(statePath, ex))

    def checkForLoadedMods(self):
        if self.jarPath is None:
            return

        loader.load.unload(self.jarPath)

    def browseForSpacehaven(self):
        import platform

        filetypes = []
        if platform.system() == "Windows":
            filetypes.append(("spacehaven.exe", "*.exe"))
            filetypes.append(("spacehaven.jar", "*.jar"))
        elif platform.system() == "Darwin":
            filetypes.append(("spacehaven.app", "*.app"))
            filetypes.append(("spacehaven.jar", "*.jar"))
        elif platform.system() == "Linux":
            filetypes.append(("all files", "*"))

        self.locateSpacehaven(
            filedialog.askopenfilename(
                parent=self.master,
                title="Locate spacehaven",
                filetypes=filetypes,
            )
        )

    # def focus(self, _arg=None):
    #    # disabled, refreshes too much and resets the selection
    #    # self.refreshModList()
    #    pass

    def refreshModList(self):
        if not self.confirm_unsaved_config("refreshing the mod list"):
            return

        try:
            # might fail at init time
            previously_selected = self.selected_mod()
        except:
            previously_selected = None

        if self.modPath is None:
            self.showModError("Spacehaven not found", "Please use the 'Find game' button below to locate Spacehaven.")
            return

        DatabaseHandler.getInstance().locateMods()
        selected_path = previously_selected.path if previously_selected else None
        self.renderModList(selected_path)

    def renderModList(self, selected_path=None):
        self._mod_list_suppress = True
        self.modList.delete(0, END)
        mod_idx = 0
        selected_idx = 0
        for mod in DatabaseHandler.getRegisteredMods():
            self.modList.insert(END, mod.title())
            mod.display_idx = mod_idx

            self.update_list_style(mod)
            if selected_path and os.path.normcase(mod.path) == os.path.normcase(selected_path):
                selected_idx = mod_idx
            mod_idx += 1

        if mod_idx:
            self.modList.selection_set(selected_idx)
        self._mod_list_suppress = False
        self.check_quick_launch()
        self.showCurrentMod()

    def show_mod_at_index(self, index):
        mods = DatabaseHandler.getRegisteredMods()
        if index < 0 or index >= len(mods):
            return
        previous_path = self.current_config_mod.path if self.current_config_mod else None
        if not self.confirm_unsaved_config("changing the selected mod"):
            self.restore_mod_selection(previous_path)
            return
        self.showMod(mods[index])

    def restore_mod_selection(self, mod_path):
        if not mod_path:
            return
        for index, mod in enumerate(DatabaseHandler.getRegisteredMods()):
            if os.path.normcase(mod.path) == os.path.normcase(mod_path):
                self._mod_list_suppress = True
                self.modList.selection_clear(0, END)
                self.modList.selection_set(index)
                self._mod_list_suppress = False
                return

    def move_current_mod(self, delta):
        mod = self.selected_mod()
        if not mod:
            return
        if not self.confirm_unsaved_config("changing mod load order"):
            return

        mods = DatabaseHandler.getRegisteredMods()
        index = mods.index(mod)
        new_index = index + delta
        if new_index < 0 or new_index >= len(mods):
            return

        mods[index], mods[new_index] = mods[new_index], mods[index]
        DatabaseHandler.getInstance().save_load_order()
        self.renderModList(mod.path)

    def update_list_style(self, mod):
        if mod.enabled:
            self.modList.itemconfig(mod.display_idx, foreground="black", selectforeground="white")
        else:
            self.modList.itemconfig(mod.display_idx, foreground="grey", selectforeground="lightgrey")

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
        if not self.confirm_unsaved_config("enabling or disabling a mod"):
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

    def create_ModConfigVariableEntry(self, configFrame: Frame, mod: ui.database.Mod, var: ui.database.ModConfigVar, row_index: int):
        bg = "#f7f7f7" if row_index % 2 == 0 else "#ffffff"
        valFrame = Frame(configFrame, bg=bg, highlightthickness=1, highlightbackground="#dddddd")
        valFrame.columnconfigure(0, weight=1)
        valFrame.columnconfigure(1, weight=0)

        labelText = var.desc or var.name
        label = Label(valFrame, text=labelText, anchor=W, justify=LEFT, bg=bg, wraplength=520)
        label.grid(row=0, column=0, sticky=EW, padx=8, pady=6)

        # Entry for value
        tk_value = StringVar(valFrame, value=var.value)

        def _value_update(name, index, mode, mod, var, tk_value):
            var.value = tk_value.get()
            self.mark_config_dirty()

        # Checkbox option
        if var.type == "toggle":
            c1 = Checkbutton(valFrame, variable=tk_value, onvalue=var.max, offvalue=var.min, bg=bg)
            c1.grid(row=0, column=1, sticky=E, padx=8, pady=6)
        # Else uses entry text
        else:
            entryValue = Entry(valFrame, textvariable=tk_value, width=28)
            entryValue.grid(row=0, column=1, sticky=E, padx=8, pady=6)

        tk_value.trace("w", lambda name, index, mode: _value_update(name, index, mode, mod, var, tk_value))

        # Link the UI variable back to the config variable for later.
        var.ui_stringvar = tk_value

        # label for debug information
        # Label(valFrame,text="").pack(side=RIGHT)

        valFrame.pack(fill=X, padx=4, pady=1)
        return

    def config_var_matches_filter(self, var, filter_text):
        if not filter_text:
            return True
        haystack = " ".join([str(var.name or ""), str(var.desc or ""), str(var.value or ""), str(var.default or "")]).lower()
        return filter_text.lower() in haystack

    def render_config_variables(self, mod):
        for child in self.modConfigListFrame.scrollable_frame.winfo_children():
            child.destroy()

        filter_text = self.config_filter_var.get().strip()
        visible_vars = [var for var in mod.variables if self.config_var_matches_filter(var, filter_text)]

        if not visible_vars:
            Label(self.modConfigListFrame.scrollable_frame, text="No matching configuration options", anchor=W).pack(fill=X, padx=8, pady=8)
            return

        for index, var in enumerate(visible_vars):
            self.create_ModConfigVariableEntry(self.modConfigListFrame.scrollable_frame, mod, var, index)

    def mark_config_dirty(self):
        if not self.current_config_mod:
            return
        self.config_dirty = True
        self.config_status_var.set("Unsaved changes")

    def set_config_clean(self, status="No unsaved changes"):
        self.config_dirty = False
        self.config_status_var.set(status)

    def discard_current_config_changes(self):
        mod = self.current_config_mod
        if mod and mod.variables:
            for var in mod.variables:
                var.value = getattr(var, "saved_value", var.value)
        self.set_config_clean("No unsaved changes")

    def save_current_config(self):
        mod = self.current_config_mod
        if not mod or not mod.variables:
            self.set_config_clean()
            return True
        if mod.saveConfig():
            self.set_config_clean("Saved")
            return True
        self.config_status_var.set("Failed to save")
        messagebox.showerror("Could not save config", "The selected mod configuration could not be saved. Check mods/modloader/logs.txt for details.")
        return False

    def confirm_unsaved_config(self, action):
        if not self.config_dirty:
            return True
        answer = messagebox.askyesnocancel(
            "Unsaved configuration changes",
            "You have unsaved configuration changes. Save before {}?\n\nYes: save changes\nNo: discard unsaved changes\nCancel: stay here".format(action),
        )
        if answer is None:
            return False
        if answer:
            return self.save_current_config()
        self.discard_current_config_changes()
        return True

    def reset_ModConfigVariables(self):
        mod = self.selected_mod()
        if not mod or not mod.variables:
            return
        for var in mod.variables:
            if hasattr(var, "ui_stringvar"):
                var.ui_stringvar.set(var.default)
            var.value = var.default
        self.mark_config_dirty()
        self.render_config_variables(mod)
        self.modConfigFrame.update()

    def update_mod_config_ui(self, mod: ui.database.Mod):
        try:
            self.modConfigFrame.destroy()
        except:
            pass

        try:
            if len(mod.variables) > 0:
                self.current_config_mod = mod
                self.config_filter_var.set("")
                self.set_config_clean()
                self.modConfigFrame = Frame(self.modDetailsWindow)
            else:
                self.current_config_mod = mod
                self.set_config_clean()
                return
        except:
            return

        configToolbar = Frame(self.modConfigFrame)
        Label(configToolbar, text="Search configuration").pack(side=LEFT, padx=4, pady=4)
        searchEntry = Entry(configToolbar, textvariable=self.config_filter_var, width=28)
        searchEntry.pack(side=LEFT, padx=4, pady=4)
        searchEntry.bind("<KeyRelease>", lambda _event: self.render_config_variables(mod))

        Button(configToolbar, text="Save config", command=self.save_current_config).pack(side=RIGHT, padx=4, pady=4)
        Button(configToolbar, text="Reset to Defaults", command=self.reset_ModConfigVariables).pack(side=RIGHT, padx=4, pady=4)
        Label(configToolbar, textvariable=self.config_status_var, anchor=E).pack(side=RIGHT, padx=8, pady=4)
        configToolbar.pack(fill=X)

        self.modConfigListFrame = ScrollableFrame(self.modConfigFrame)
        self.modConfigListFrame.pack(fill=BOTH, expand=True)
        self.render_config_variables(mod)

        self.modConfigFrame.update()
        self.modDetailsWindow.add(self.modConfigFrame, minsize=180)
        self.modDetailsWindow.update()

    def showMod(self, mod: ui.database.Mod):
        if not mod:
            return self.showModError("No mods found", "Please install some mods into your mods folder.")

        title = mod.title()
        if mod.enabled:
            command_label = "Disable"
        else:
            command_label = "Enable"
            title += " [DISABLED]"

        self.modDetailsName.config(text=title)
        self.modEnableDisable.config(text=command_label)
        self.update_description(mod.getDescription())
        self.update_mod_config_ui(mod)

    def showModError(self, title, error):
        self.modDetailsName.config(text=title)
        self.update_description(error)

    def openModFolder(self):
        ui.launcher.open(self.modPath[0])

    def set_ui_state(self, state, message):
        self.launchButton.config(state=state, text=message)
        self.modEnableDisable.config(state=state)
        self.spacehavenBrowse.config(state=state)
        self.quickLaunchClear.config(state=state)
        self.modListRefresh.config(state=state)
        self.modListOpenFolder.config(state=state)
        self.modMoveUp.config(state=state)
        self.modMoveDown.config(state=state)
        self.extractButton.config(state=state)
        self.annotateButton.config(state=state)
        self.quitButton.config(state=state)

    can_quit = True

    def disable_UI(self, message):
        self.set_ui_state(DISABLED, message)
        # Handle OS dependent specific cursor
        os_name = platform.system()
        if os_name == "Windows":
            self.config(cursor="wait")
        else:
            self.config(cursor="watch")
        self.can_quit = False

    def enable_UI(self, message):
        self.set_ui_state(NORMAL, message)
        self.config(cursor="")
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

        # daemon=True so the interpreter can still exit if the GUI goes away
        # while a task (e.g. waiting on the launched game) is blocked; without
        # it the loader lingers as a headless process (issue #74).
        self.background_thread = threading.Thread(target=_wrapper, daemon=True)
        self.background_thread.start()
        self.after(self.background_refresh_delay, self.update_background_state)

    def update_background_state(self):
        extra_label = "." * (self.background_counter % 5)
        self.background_counter += 1

        self.launchButton.config(text=extra_label + " " + ui.log.logger.backgroundState + " " + extra_label)
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
        ui.launcher.open(os.path.join(corePath, "library"))

    def annotate(self):
        corePath = self._core_extract_path()
        ui.log.log(f"Annotating and putting files in {corePath}")
        try:
            annotate(corePath)
        except Exception as e:
            ui.log.log("  Error during annotation!")
            ui.log.log(repr(e))

        ui.launcher.open(os.path.join(corePath, "library"))

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
        md5 = hashlib.md5(text_sig.encode("utf-8")).hexdigest()
        return md5

    def quick_launch_available(self):
        mods_sig = self.current_mods_signature()
        return os.path.isfile(loader.load.quick_launch_filename(mods_sig, self.jarPath))

    def check_quick_launch(self):
        has_cache = self.jarPath and loader.load.has_quick_launch_cache(self.jarPath)
        if not self.mods_enabled():
            self.launchButton_default_text = "LAUNCH ORIGINAL GAME"
        elif self.quick_launch_available():
            self.launchButton_default_text = "QUICKLAUNCH!"
        else:
            self.launchButton_default_text = "LAUNCH!"
        self.quickLaunchClear.config(state=NORMAL if has_cache else DISABLED)
        self.launchButton.config(text=self.launchButton_default_text)

    def clear_quick_launch(self):
        if not self.jarPath:
            return
        if not messagebox.askyesno("Clear QuickLaunch cache", "Delete all cached QuickLaunch files for this Mod Loader install?"):
            return
        removed = loader.load.clear_quick_launch_cache(self.jarPath)
        ui.log.log("Cleared {} QuickLaunch cache file(s).".format(removed))
        self.check_quick_launch()

    def launch_wrapper(self):
        if self.config_dirty:
            answer = messagebox.askyesnocancel(
                "Unsaved configuration changes",
                "You have unsaved configuration changes. Save before launching?\n\nYes: save and launch\nNo: launch without saving\nCancel: stay here",
            )
            if answer is None:
                return
            if answer and not self.save_current_config():
                return
            if answer is False:
                self.launch_without_saving_config = True

        try:
            DatabaseHandler.getInstance().reconcile_jarmod_classpath()
        except Exception as ex:
            ui.log.log("Failed to run JAR classPath cleanup before launch: {}".format(ex))

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
        except:
            import traceback

            traceback.print_exc()
            messagebox.showerror("Error during quick launch", traceback.format_exc(3))

    def patchAndLaunch(self):
        activeMods = DatabaseHandler.getActiveMods()

        # JAR mods are injected into the game through config.json's classPath
        # (handled in JarMod.enable() during mod discovery), but they can ALSO
        # ship traditional XML modifications under library/ and patches/ just
        # like any XML mod. Pass every active mod through the XML pipeline so
        # those modifications are merged in too.

        if getattr(self, "launch_without_saving_config", False):
            ui.log.log("Skipping config autosave because user chose to launch without saving.")
            self.launch_without_saving_config = False
        else:
            # If any active mods have variables, save them.
            for mod in activeMods:
                if mod.variables:
                    mod.saveConfig()

        try:
            loader.load.load(self.jarPath, activeMods, self.current_mods_signature())
            ui.launcher.launchAndWait(self.gamePath)
            loader.load.unload(self.jarPath)
        except:
            import traceback

            traceback.print_exc()
            messagebox.showerror("Error loading mods", traceback.format_exc(3))

    def quit(self):
        if not self.confirm_unsaved_config("quitting"):
            return
        if self.can_quit:
            self.master.destroy()
            return

        messagebox.showerror("Error", "Cannot quit while a task is running!")


def handleException(type, value, trace):
    message = "".join(traceback.format_exception(type, value, trace))

    ui.log.log("!! Exception !!")
    ui.log.log(message)

    messagebox.showerror("Error", "Sorry, something went wrong!\n\n" "Please open an issue at https://github.com/Spacehaven-modding-tools/spacehaven-modloader and attach logs.txt from your mods/modloader/ folder.")


if __name__ == "__main__":
    root = Tk()

    # Pick a default window size that fits the user's screen. SteamDeck is
    # 1280x800 native, so cap height at 720 and width at 1280, while staying
    # within ~85% of the available screen.
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    win_w = max(800, min(1280, int(screen_w * 0.85)))
    win_h = max(600, min(720, int(screen_h * 0.85)))
    root.geometry("{}x{}".format(win_w, win_h))
    root.minsize(800, 600)
    root.report_callback_exception = handleException

    # HACK: Button labels don't appear until the window is resized with py2app
    def fixNoButtonLabelsBug():
        root.geometry("{}x{}".format(win_w, win_h + 1))

    root.resizable(True, True)

    app = Window(root)
    root.update()
    root.update_idletasks()
    root.after(0, fixNoButtonLabelsBug)
    root.protocol("WM_DELETE_WINDOW", app.quit)
    if platform.system() == "Darwin":
        # Cmd+Q is delivered through Tk's tk::mac::Quit handler, not
        # WM_DELETE_WINDOW. Without this, Tk's default handler terminates the
        # process immediately: quit() never runs, the game jar is left patched,
        # and the launch thread is abandoned (issue #74).
        root.createcommand("tk::mac::Quit", app.quit)
    icon = None
    try:
        icon = PhotoImage(file="spacehaven-modloader.png")
    except:
        pass
    if icon is None:
        try:
            icon = PhotoImage(file="./_internal/spacehaven-modloader.png")
        except:
            pass
    if icon is not None:
        root.iconphoto(True, icon)
    root.mainloop()
