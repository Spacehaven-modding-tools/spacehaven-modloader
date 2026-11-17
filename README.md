# Space Haven Mod Loader

A modding tool for [Space Haven by Bugbyte](https://bugbyte.fi/spacehaven/).

See the [change log](CHANGELOG.md) for version history.

## Getting Started

Download the Mod Loader from the repository's **Releases** page, or see [DEVELOPERS.md](DEVELOPERS.md) to run it from source. On Windows, install the Mod Loader in a separate folder from the game.

If you installed the Mod Loader through Steam Workshop, follow [Bugbyte's Steam setup guide](https://store.steampowered.com/news/app/979110/view/687504475423769186). In the Steam Library, select the `play_with_mods` beta for Space Haven, wait for the Workshop download, then choose **Play With Mods** when launching the game.

![Screenshot](/tools/screenshot.png?raw=true)

1. Confirm the game path, or select your installation with **Find game**.

2. Click the "Open Mods Folder" button to open your game's `mods` folder.

3. Download some mods and copy them into the `mods` folder. Mods can be found on [NexusMods](https://www.nexusmods.com/spacehaven). When you're done your game folder should look something like this:

```
spacehaven.jar
savegames/
  ...
mods/
  BetterToilets/
    info.xml
    library/
      haven.xml
      animations.xml
      textures.xml
    textures/
      2283.png
  ClaimDerelict/
    info.xml
    ClaimDerelict.jar
  ...
```

4. Go back to the mod loader and make sure the mods you installed appear in the list. If they don't then you might not have installed them properly. Double check the folder structure.

5. Click **Launch**. The loader builds a separate JAR when enabled mods change game assets.

6. QuickLaunch stores generated JARs under `mods/modloader`. Changes to the game, mods, or load order invalidate the cache. Use **Clear QuickLaunch cache** to remove cached JARs for the current installation.

The Mod Loader also writes its diagnostics log and small state files to `SpaceHaven/mods/modloader` after the game folder is detected.

### Troubleshooting Steam and Workshop

- If the launcher opens, select **Mod Discovery** to see the game installation, the Steam library and Workshop folder, and the results of the last mod scan. Use **Refresh Mods** after Steam finishes downloading items.
- If the window fails to open after the loader starts, look for `startup.log` in `%LOCALAPPDATA%\spacehaven-modloader` on Windows, `~/Library/Logs/spacehaven-modloader` on macOS, or `${XDG_STATE_HOME:-~/.local/state}/spacehaven-modloader` on Linux. Compare its timestamp with the last attempt. If Steam never starts the loader, there will be no new startup log.
- Use **Export logs** to collect the startup log and available game logs in a local ZIP. Review the archive for personal paths or identifiers before sharing it.

## Java Runtimes

**Java 8** uses the runtime bundled with the game. **Java 25** and **Java 27** use Eclipse Temurin.

1. Select **Java 25** or **Java 27** and click **Install Java + AspectJ**. The loader verifies both downloads with SHA-256.
2. Click **Check runtime** to verify the installation and launch configuration. Use **Classpath** to review the JARs selected for the next launch.
3. To return to the bundled runtime, select **Java 8**.

On Java 25 and 27, DateFix replaces narrow and non-breaking spaces in the timestamps shown in the local and cloud save lists. The loader stores downloaded runtimes per game installation under `mods/modloader/runtimes`.

## Configuration and Load Order

Mods that expose configuration variables can be edited in the selected mod's configuration panel. Large configuration lists can be scrolled and filtered with the search field.

Use **Save config** to write changes to the mod's `info.xml`. The loader shows whether there are unsaved changes and warns before switching mods, disabling mods, launching, or quitting with pending changes.

Use **Move up** and **Move down** to adjust load order. The selected order is saved in `modloader_load_order.json` next to `spacehaven.jar`.

## Workshop JAR Mods

The loader discovers JAR mods in the selected Steam library's Workshop directory. Enable them in the mod list before launching the game.

Modders working on JAR/AspectJ mods can find internals (classpath handling, asset resolution conventions) in [DEVELOPERS.md](DEVELOPERS.md) and in the [SpaceHavenModTemplate](https://github.com/Spacehaven-modding-tools/SpaceHavenModTemplate) repository.

## Known issues

Steam Cloud, Steam account integration, and in-game restarts need further testing with the direct Java launcher.

## Modding Guide

There are two types of mods supported by the modloader. These are XML mods, which are used to create new buildings, and code injection mods that can alter game functionality. Info on both types of mods is below.

### Code Injection Mods
These mods use AspectJ (similar to Harmony in C#) to allow you to inject code before, after, and around the game's existing functions, method calls, and field accesses. This functionality makes code injection mods extremely powerful, but they require programming knowledge (or patience and a willingness to learn) to create. You'll also want a tool that allows you to decompile `spacehaven.jar`. I recommend [JD GUI](https://github.com/java-decompiler/jd-gui) as it seemed to work the best out of the few options I tried. The game's code is not obfuscated, so the decompilation process is relatively painless. 

There's a [template repo](https://github.com/Spacehaven-modding-tools/SpaceHavenModTemplate) that you can use as a basis for creating your own code injection mod. The template repo includes instructions on how to set up your dev environment as well as some basic sample mods.

#### Effective classpath

The loader reads `config.json` beside the selected game JAR. It builds the classpath for the current session from enabled local and Workshop mods. **Classpath** shows excluded entries from the configuration and the effective order. Use a relative manifest dependency contained in the mod for companion JARs outside its top level.

The launcher selects its entry point from the game JAR manifest. It uses the original game JAR unless an enabled mod changes game assets.

#### Asset resolution for JAR mods

Java mods that need external assets should not assume a fixed `SpaceHaven/mods/<ModName>` layout, because the same mod may also be installed from Workshop. The two supported patterns are:

1. **Bundle assets inside the JAR** and read them via `getResource()` / `getResourceAsStream()`.
2. **Resolve files relative to the JAR's own location** using `getProtectionDomain().getCodeSource().getLocation()`. Example:

   ```java
   URL jarUrl = MyMod.class.getProtectionDomain()
       .getCodeSource()
       .getLocation();
   Path modDir = Paths.get(jarUrl.toURI()).getParent();
   Path config = modDir.resolve("mystuff/config.json");
   ```

Either pattern works equally well for local and Workshop installations and avoids relying on a global classpath registry.


### XML Mods

XML Mods are stored as a series of XML files in roughly the same format as the game's library.

You can take a look at the library by clicking the "Extract game assets" button. That will extract the game library from `spacehaven.jar` into `mods/spacehaven/` and open the folder.

Once that's done, you can also click "Annotate XML":
The main file of interest is `library/haven_annotated.xml`, which is an annotated copy of `library/haven`, which is the main game library. It contains definitions for most of the things in the game (buildings, items, ships, characters, objectives, generation parameters, etc). Also of interest are `library/texts`, `library/animations`, and `library/textures`.

`library/animations_annotated.xml` will be created as well, with the textures names for some of the individual blocks I have personnally used. You can add/change textures names by editing the the `textures_annotations.xml` file in the modloader directory. You should copy the corresponding line from `library/textures` and add an `_annotation` tag with the name that makes sense for you, after finding the textures of interest in `library/textures.exploded/`.

Mods follow the same folder structure and file format and should be reasonably obvious from the included sample mods.

Note that because mods are loaded by doing an id-wise merge with the base game library, only the following files and tags are currently supported:
- All definitions in `library/haven`
- `animations` in `library/animations`
- `t`s and `re`s in `library/textures`
- `t`s in `library/texts`


#### ID Numbers

Most of the items in the game's library are identified by a numeric ID rather than a human-readable name.

If you want to replace an *existing* game definition, like the included Greenhouse mod does, simply copy that definition into to your mod with the same ID number that the game uses. The mod loader will replace the game's definition with the one from your mod.

If you want to create a *new* definition, things get a bit trickier because you need to make sure your ID numbers are unique across all mods that might get loaded. Luckily IDs can be any (positive) 32-bit integer which means there's lots of space.

I recommend prefixing your definition IDs with your Discord user number (e.g. mine is #4511) and a sequential mod number (e.g. I used `00` for the `artificial-plant` example, `01` for `exterior-air-vent`, etc) to come up with something reasonably unique, e.g. `451102000` for the Monster Meat crop recipe in the `greenhouse` example (and then `451102001` for the next ID in that mod, `451102002` for the one after that, etc etc).


#### Navigating the Library

Since ID numbers are unique, they're reasonably easy to follow in a text editor – if you find a definition that references another, simply search for the referenced ID that you're interested in.

To find human-readable names, look for a `tid="###"` attribute and search for that ID in `library/texts`. Or, conversely, find the text in `library/texts` and search for the corresponding ID in `library/haven`.

For example, suppose we want to find the "Life Support" building. Starting from `/library/texts` and searching for "Life Support" we find:

```
    <lifeSupportName id="140" pid="139">
        <EN>Life Support</EN>
    </lifeSupportName>
```

We can then search for `tid="140"` in `library/haven` to find its definition:
```
    <me mid="927" ...>
        ...
        <objectInfo ...>
            ...
            <name tid="140" />
            <desc tid="141" />
            <subCat id="1508" />
            ...
        </objectInfo>
    </me>
```

Here we can see that the life support unit's ID is `mid="927"` and its build (sub-)category is `<subCat id="1508" />`. Searching for that ID we can find:

```
        <cat disabled="false" id="1508" order="3">
            <mainCat id="1505" />
            <button instance="536_BuildCatButtons1_subCat" />
            <name tid="869" />
        </cat>
```

and looking up the `<name tid="869" />` we see the category is named:

```
    <lifesupport id="869" pid="874">
        <EN>LIFE SUPPORT</EN>
    </lifesupport>
```

To make life easier, the mod loader does these name lookups automatically in a few places and stores the results in `_annotated_name=""` attributes. This annotated version of the library is saved to `library/haven.annotated.xml` and is (accordingly) a bit easier to navigate.


#### Textures and Animations

Extracting and annotating game assets also decodes and explodes the game's textures into `library/textures.exploded`. The game's original packed textures are written to `library/textures.exploded/*.png` and the texture regions are written to `library/textures.exploded/*/*.png`, where the folder name is the texture ID and the filename is the region ID.

Regions definitions can be found in `library/textures.xml` in `<re n="..." />` tags and are used in `library/animations.xml` by the `<assetPos a="..." />` tags.

The loader can overwrite existing textures from the base game and add new ones. To overwrite a texture, simply place a file called `123.png` in a directory called `textures` (where 123 is the id of the texture you want to replace). 

To add a new texture, you need to add a `<re n="..." t="..." />` entry in `library/textures.xml`. Textures are packed together in `.cim` files, which are defined in `<t i="..." />` entries. The `re` entry references the `t` entry through it's index `i`. Take care of choosing reasonably unique indexes to avoid conflicts. Once this is done, you can add the `123456.png` file to the `textures` directory. 

To inspect the packed output, extract the textures from the generated QuickLaunch JAR.
