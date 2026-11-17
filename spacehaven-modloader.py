#!/usr/bin/env python3

import os
import platform
import sys
import threading
import hashlib
import tempfile
import traceback
import webbrowser
from pathlib import Path
import ui.log

try:
    import vdf
    from tkinter import *
    from tkinter import filedialog, messagebox, ttk, font, scrolledtext

    import loader.extract
    import loader.load
    import ui.database
    from loader.assets.annotate import annotate
    from ui.gameinfo import GameInfo
    import ui.header
    import ui.launcher
    from ui import launch_config, launch_session, runtime_manager
    from ui.cache_fingerprint import mod_fingerprint
    import ui.paths
    import version
    from ui.scrolledlistbox import ScrolledListbox
except Exception:
    if __name__ == "__main__":
        with ui.log.logger.startup_logging():
            raise
    raise

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
STEAM_SETUP_GUIDE = "https://store.steampowered.com/news/app/979110/view/687504475423769186"


def _read_text_file(path):
    with open(path, "r", encoding="utf-8") as inFile:
        return inFile.read()


def _write_text_file(path, value):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".shl-pref-", dir=target.parent) as scratch:
        stage = Path(scratch) / target.name
        stage.write_text(value, encoding="utf-8")
        os.replace(stage, target)


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

        runtimeFrame = self.runtimeFrame = Frame(self)
        self.runtime_options = {
            "Java 8": runtime_manager.MODE_ORIGINAL,
            "Java 25": runtime_manager.MODE_TEMURIN25,
            "Java 27": runtime_manager.MODE_TEMURIN,
        }
        self.runtime_label = Label(runtimeFrame, text="Java runtime:")
        self.runtime_label.pack(side=LEFT, padx=(8, 2), pady=4)
        self.runtime_choice = StringVar(value="Java 8")
        self.runtime_selector = ttk.Combobox(runtimeFrame, textvariable=self.runtime_choice, values=list(self.runtime_options), state="readonly", width=12)
        self.runtime_selector.pack(side=LEFT, padx=2, pady=4)
        self.runtime_selector.bind("<<ComboboxSelected>>", self.on_runtime_selected)
        self.installJavaButton = Button(runtimeFrame, text="Install Java + AspectJ", command=self.install_selected_java)
        self.installJavaButton.pack(side=LEFT, padx=6, pady=4)
        self.testRuntimeButton = Button(runtimeFrame, text="Check runtime", command=self.test_selected_runtime)
        self.testRuntimeButton.pack(side=LEFT, padx=4, pady=4)
        self.exportLogsButton = Button(runtimeFrame, text="Export logs", command=self.export_launch_logs)
        self.classpathButton = Button(runtimeFrame, text="Classpath", command=self.show_classpath_diagnostics)
        self.classpathButton.pack(side=LEFT, padx=4, pady=4)
        Button(runtimeFrame, text="Mod Discovery", command=self.show_mod_discovery).pack(side=LEFT, padx=4, pady=4)
        self.exportLogsButton.pack(side=LEFT, padx=4, pady=4)

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

        buttonFrame.pack(fill=X, padx=4, pady=4)
        runtimeFrame.pack(fill=X, padx=6, pady=(0, 6))

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
            preference = ui.paths.loader_directory() / loader.load.PREVIOUS_GAME_PATH_FILENAME
            location = _read_text_file(preference).strip()
            if Path(location).is_absolute() and Path(location).exists() and self.locateSpacehaven(location):
                return
            ui.log.log(f"Saved game path could not be used: {location}")
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

            libraries_file = Path(steam_path, "steamapps", "libraryfolders.vdf")
            ui.log.log(f"Checking Steam libraries in {libraries_file}")
            with libraries_file.open(encoding="utf-8-sig") as source:
                libraries = vdf.parse(source)["libraryfolders"]
            for library in libraries.values():
                if not isinstance(library, dict) or "979110" not in library.get("apps", {}):
                    continue
                executable = Path(library["path"], "steamapps", "common", "SpaceHaven", game_executable)
                if executable.exists() and self.locateSpacehaven(executable):
                    return
                ui.log.log(f"Steam library lists Space Haven, but the game path could not be used: {executable}")

        except FileNotFoundError:
            ui.log.log("Unable to locate Steam registry keys or library paths, aborting Steam autolocator")
        except Exception as ex:
            ui.log.log("Unable to use Steam autolocator: {}".format(ex))

        # Brute force method
        for location in POSSIBLE_SPACEHAVEN_LOCATIONS:
            try:
                location = ui.paths.loader_directory() / Path(location).expanduser()
                if location.exists() and self.locateSpacehaven(location):
                    return
            except Exception as ex:
                ui.log.log("Unable to check possible Space Haven location {}: {}".format(location, ex))
        ui.log.log("Unable to autolocate installation. User will need to pick manually.")

    def locateSpacehaven(self, path):
        if not path:
            return False
        path = str(Path(path).resolve())
        game_jar = runtime_manager.game_directory(path) / "spacehaven.jar"
        backup = game_jar.with_suffix(".jar.vanilla")
        if not game_jar.is_file():
            if not backup.is_file() or not messagebox.askyesno(
                "Legacy game recovery",
                f"Restore missing {game_jar.name} from the validated legacy backup?\n\n{backup}",
            ):
                self.showModError("Space Haven JAR missing", str(game_jar))
                return False
            try:
                with launch_session.installation_lock(path):
                    loader.load.restore_missing_legacy_jar(game_jar)
            except Exception as exc:
                self.showModError("Legacy recovery failed", str(exc))
                return False

        if path.lower().endswith(".app"):
            self.gamePath = path
            self.jarPath = path + "/Contents/Resources/spacehaven.jar"
            self.modPath = path + "/Contents/Resources/mods"

        else:
            self.gamePath = path
            self.jarPath = str(game_jar)
            self.modPath = os.path.join(os.path.dirname(path), "mods")

        if not os.path.exists(self.modPath):
            os.mkdir(self.modPath)

        ui.log.setGameModPath(self.modPath)
        ui.log.log("Discovered game at {}".format(path))
        ui.log.log("  gamePath: {}".format(self.gamePath))
        ui.log.log("  modPath: {}".format(self.modPath))
        ui.log.log("  jarPath: {}".format(self.jarPath))

        self.save_previous_spacehaven_path(path)

        self.gameInfo = GameInfo(self.jarPath)

        self.spacehavenText.delete(0, "end")
        self.spacehavenText.insert(0, self.gamePath)

        saved_mode = runtime_manager.get_mode(self.gamePath)
        for text, mode in self.runtime_options.items():
            if mode == saved_mode:
                self.runtime_choice.set(text)
                break

        self.modPath = [self.modPath]
        DatabaseHandler(self.modPath, self.gameInfo)
        self.refreshModList()
        return True

    def modloader_state_file(self, filename):
        return loader.load.modloader_state_file(self.jarPath, filename)

    def save_previous_spacehaven_path(self, path):
        # Stored next to the executable so we can read it before knowing where
        # Space Haven lives. Moving this file into <SpaceHaven>/mods/modloader
        # would break the bootstrap on the next launch.
        targetPath = ui.paths.loader_directory() / loader.load.PREVIOUS_GAME_PATH_FILENAME
        try:
            _write_text_file(targetPath, path)
            ui.log.log("Saved previous Space Haven path to {}".format(os.path.abspath(targetPath)))
        except Exception as ex:
            ui.log.log("Unable to save previous Space Haven path to {}: {}".format(os.path.abspath(targetPath), ex))

    def load_extra_mod_paths(self):
        state_path = self.modloader_state_file(loader.load.EXTRA_MODS_PATH_FILENAME)
        try:
            extra_paths = _read_text_file(state_path)
        except FileNotFoundError:
            if (ui.paths.loader_directory() / loader.load.EXTRA_MODS_PATH_FILENAME).is_file():
                ui.log.log(f"Legacy extra mod roots require per-install selection. Copy the intended absolute paths to {state_path}.")
            return
        except OSError as exc:
            ui.log.log(f"Unable to read extra mod paths from {state_path}: {exc}")
            return
        for value in extra_paths.splitlines():
            if not value.strip():
                continue
            candidate = Path(value.strip()).expanduser()
            if candidate.is_absolute():
                self.modPath.append(str(candidate))
            else:
                ui.log.log(f"Skipping relative extra mod root: {value}")

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

        if not isinstance(self.modPath, list):
            self.showModError("Spacehaven not found", "Please use the 'Find game' button below to locate Spacehaven.")
            return

        self.workshopPath = ui.paths.resolve_workshop_path(self.gamePath)
        for line in self.workshop_discovery():
            ui.log.log(line)
        self.modPath = [self.modPath[0]]
        if self.workshopPath:
            self.modPath.append(self.workshopPath)
        self.load_extra_mod_paths()
        database = DatabaseHandler.getInstance()
        database.path_list = self.modPath
        database.locateMods()
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

    def selected_runtime_mode(self):
        return self.runtime_options.get(self.runtime_choice.get(), runtime_manager.MODE_ORIGINAL)

    def on_runtime_selected(self, _event=None):
        if not self.gamePath:
            return
        try:
            runtime_manager.set_mode(self.gamePath, self.selected_runtime_mode())
            ui.log.log("Selected Java runtime mode: " + self.selected_runtime_mode())
        except Exception as exc:
            messagebox.showerror("Java runtime selection", str(exc))

    def _selected_java_major(self):
        return {runtime_manager.MODE_TEMURIN: 27, runtime_manager.MODE_TEMURIN25: 25}.get(self.selected_runtime_mode())

    def install_selected_java(self):
        if not self.gamePath:
            messagebox.showerror("Java runtime", "Find Space Haven first.")
            return
        major = self._selected_java_major()
        if major is None:
            messagebox.showinfo("Java runtime", "Select Java 25 or Java 27 first. Java 8 uses the runtime bundled with the game.")
            return
        if self.background_thread is not None:
            return
        if not messagebox.askyesno(
            f"Install Java {major}",
            f"Install Temurin {major} from Eclipse Adoptium and AspectJ 1.9.27 from Maven Central?\n\n"
            "Both downloads are checked against SHA-256 and stored under mods/modloader.",
        ):
            return

        path = self.gamePath

        def task():
            from ui import aspectj_runtime
            with launch_session.installation_lock(path):
                java = runtime_manager.install_temurin(path, major=major, log=ui.log.log)
                weaver = aspectj_runtime.install_aspectj(path, log=ui.log.log)
                ui.log.log(f"Java {major} ready: {java}")
                ui.log.log(f"AspectJ {aspectj_runtime.VERSION} ready: {weaver}")
            return f"Temurin {major} and AspectJ {aspectj_runtime.VERSION} installed."

        self.start_background_task(task, f"Installing Java {major}")

    def test_selected_runtime(self):
        if not self.gamePath:
            messagebox.showerror("Test JVM", "Find Space Haven first.")
            return
        path = self.gamePath
        mode = self.selected_runtime_mode()
        self.start_background_task(lambda: runtime_manager.preflight(path, mode), "Checking JVM and AspectJ")

    def workshop_discovery(self):
        steamapps = ui.paths.resolve_steamapps(self.gamePath)
        if steamapps is None:
            return ["Steam library: unavailable for this installation."]
        library = steamapps.parent
        workshop = steamapps / "workshop" / "content" / ui.paths.SPACE_HAVEN_APP_ID
        if self.workshopPath is None:
            return [f"Steam library: {library}", f"Workshop folder unavailable: {workshop}"]
        return [f"Steam library: {library}", f"Workshop folder: {self.workshopPath}"]

    def show_mod_discovery(self):
        startup = ui.log.logger.startupPath
        lines = [f"Startup log: {startup}" if startup else "Startup log: unavailable."]
        if self.gamePath and isinstance(self.modPath, list):
            database = DatabaseHandler.getInstance()
            lines += [f"Game: {self.gamePath}", *self.workshop_discovery(), ""]
            lines.append(f"Mods found: {len(database.mods)} ({len(database.getActiveMods())} enabled)")
            lines.extend(database.discovery)
        else:
            lines += ["", "Space Haven was not found. Use Find game to select its installation."]

        window = Toplevel(self.master)
        window.title("Mod Discovery")
        window.transient(self.master)
        details = scrolledtext.ScrolledText(window, wrap=WORD, width=84, height=22)
        details.insert("1.0", "\n".join(lines))
        details.configure(state=DISABLED)
        details.pack(fill=BOTH, expand=True, padx=10, pady=10)
        ttk.Button(window, text="Steam Setup Guide", command=lambda: webbrowser.open(STEAM_SETUP_GUIDE)).pack(side=LEFT, padx=10, pady=(0, 10))
        ttk.Button(window, text="Close", command=window.destroy).pack(side=RIGHT, padx=10, pady=(0, 10))

    def export_launch_logs(self):
        """Export only launch logs, with user confirmation about personal paths."""
        startup = ui.log.logger.startupPath
        if not (self.gamePath or startup):
            messagebox.showinfo("Export logs", "No logs are available yet.")
            return
        if not messagebox.askyesno("Export diagnostics", "Logs can contain Windows usernames, installation paths and mod names.\n\nCreate a local ZIP to inspect before sharing?"):
            return
        try:
            from ui import diagnostics
            target = filedialog.asksaveasfilename(title="Save Space Haven diagnostics", defaultextension=".zip", filetypes=[("ZIP archive", "*.zip")], initialfile="SHL-diagnostics.zip")
            if not target:
                return
            files = diagnostics.export_logs(self.gamePath, target, startup_log=startup)
            messagebox.showinfo("Diagnostics exported", "Saved {} log files to:\n{}\n\nReview the contents before sharing.".format(files, target))
        except Exception as exc:
            ui.log.log("Diagnostics export failed: {}".format(exc))
            messagebox.showerror("Diagnostics export failed", str(exc))

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
        self.installJavaButton.config(state=state)
        self.testRuntimeButton.config(state=state)
        self.exportLogsButton.config(state=state)
        self.classpathButton.config(state=state)
        self.modList.config(state=state)
        self.runtime_selector.config(state="readonly" if state == NORMAL else "disabled")

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

        self.background_error = None
        self.background_result = None
        self.background_finished = False
        # for counting the iterations in update_background_state
        self.background_counter = 0

        def _wrapper():
            try:
                self.background_result = task()
            except Exception as exc:
                self.background_error = str(exc)
                ui.log.log(traceback.format_exc())
            finally:
                self.background_finished = True

        self.background_thread = threading.Thread(target=_wrapper)
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
            if self.background_error:
                messagebox.showerror("Mod Loader task failed", self.background_error)
            elif self.background_result:
                messagebox.showinfo("Mod Loader", self.background_result)
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
        annotate(corePath)

        ui.launcher.open(os.path.join(corePath, "library"))

    def mods_enabled(self):
        return DatabaseHandler.getActiveMods()

    def check_quick_launch(self):
        has_cache = self.jarPath and loader.load.has_quick_launch_cache(self.jarPath)
        self.launchButton_default_text = "LAUNCH WITHOUT MODS" if self.jarPath and not self.mods_enabled() else "LAUNCH!"
        self.quickLaunchClear.config(state=NORMAL if has_cache else DISABLED)
        self.launchButton.config(text=self.launchButton_default_text)

    def clear_quick_launch(self):
        if not self.jarPath:
            return
        if not messagebox.askyesno("Clear QuickLaunch cache", "Delete cached QuickLaunch files for this installation?"):
            return

        def clear():
            with launch_session.installation_lock(self.gamePath):
                removed = loader.load.clear_quick_launch_cache(self.jarPath)
                ui.log.log(f"Cleared {removed} QuickLaunch file(s).")

        self.start_background_task(clear, "Clearing QuickLaunch")

    def show_classpath_diagnostics(self):
        if not self.jarPath:
            return
        mode, game, jar, mods = self.selected_runtime_mode(), self.gamePath, self.jarPath, self.mods_enabled()

        def diagnose():
            java, major = runtime_manager.selected_java(game, mode)
            lines = []
            launch_config.build(game, jar, mods, java, major, report=lines.append)
            return "\n\n".join(lines)

        self.start_background_task(diagnose, "Inspecting classpath")

    def launch_wrapper(self):
        if not self.jarPath or not self.confirm_unsaved_config("launching"):
            return
        game_executable = self.gamePath
        jar = Path(self.jarPath)
        mods = self.mods_enabled()
        mode = self.selected_runtime_mode()
        version = self.gameInfo.version

        def launch():
            with launch_session.installation_lock(game_executable) as process_file:
                java, major = runtime_manager.selected_java(game_executable, mode)
                java_version = runtime_manager.verify_java(java, major)
                backup = jar.with_suffix(".jar.vanilla")
                if backup.exists():
                    with jar.open("rb") as live, backup.open("rb") as legacy:
                        if hashlib.file_digest(live, "sha256").digest() != hashlib.file_digest(legacy, "sha256").digest():
                            raise RuntimeError(
                                f"{jar.name} differs from its legacy .vanilla backup. Verify the installed game and retain the backup for review."
                            )
                # Validate classpath and launch options before building the cache.
                launch_config.build(game_executable, jar, mods, java, major)
                game_jar = jar
                if mods:
                    def fingerprint():
                        return mod_fingerprint(mods, version, jar)

                    game_jar = loader.load.prepare_game_jar(jar, mods, fingerprint(), fingerprint)
                else:
                    game_jar = loader.load.prepare_game_jar(jar, [], None)
                ui.launcher.run(game_executable, game_jar, mods, java, major, java_version, process_file)

        self.start_background_task(launch, "Preparing Space Haven")

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


def main():
    with ui.log.logger.startup_logging():
        ui.log.log(f"Loader directory: {ui.paths.loader_directory()}")
        ui.log.log(f"Working directory: {Path.cwd()}")
        if getattr(sys, "frozen", False):
            ui.log.log(f"Loader executable: {sys.executable}")
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

        # A resize makes button labels appear in py2app builds.
        def fixNoButtonLabelsBug():
            root.geometry("{}x{}".format(win_w, win_h + 1))

        root.resizable(True, True)

        app = Window(root)
        root.protocol("WM_DELETE_WINDOW", app.quit)
        root.after(0, fixNoButtonLabelsBug)
        app_dir = ui.paths.loader_directory()
        for path in (app_dir / "spacehaven-modloader.png", app_dir / "_internal" / "spacehaven-modloader.png"):
            try:
                icon = PhotoImage(file=str(path))
            except TclError:
                continue
            root.iconphoto(True, icon)
            break
        ui.log.log("Mod Loader window initialized.")
    root.mainloop()


if __name__ == "__main__":
    main()
