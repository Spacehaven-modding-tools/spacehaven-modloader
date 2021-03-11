# Space Haven Mod Loader

This is an unofficial modding tool for [Space Haven by Bugbyte](http://bugbyte.fi/spacehaven/), an early-alpha spaceship colony sim.

It is **not associated with Bugbyte or Space Haven in any way** other than that it makes some modding possible for the game. This tool is intended to be a sneak peek at what modding might be able to do, and in the future it will be replaced by official mod support.


## Getting Started

Download the [latest release](https://github.com/PhiR42/spacehaven-modloader/releases/download/0.0.7/spacehaven-modloader-win-amd64.zip) and fire it up.

![Screenshot](/tools/screenshot.png?raw=true)

1. Make sure it found where you installed Space Haven. If it didn't, you'll need to locate it manually via the "Browse..." button in the top right corner.

2. Click the "Open Mods Folder" button to open your game's `mods` folder.

3. Download some mods and copy them in. There are a few example mods available from [the releases page](https://github.com/anatarist/spacehaven-modloader/releases) or you can find them elsewhere on the internet. When you're done your game folder should look something like this:

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
  ...
```

4. Go back to the mod loader and make sure the mods you installed appear in the list. If they don't then you might not have installed them properly. Double check the folder structure.

5. When you're ready click "Launch Space Haven!" to play with mods. The mod loader will load the mods into the game, launch the game, and then unload them again when the game exits.

6. Once you've played with a given set of mods, the loader will keep a quick launch file for them. The next time they will load a lot faster. If you want to develop your own mod or tweak one, you should always click on "Clear QuickLaunch file" before running the game, so your changes are taken into account. 

## Known issues

If you change the language or restart the game from within itself, the modloader will think the game has quit and will throw an error. Nothing permanent.

Running the game from the modloader will not load your cloud credentials correctly. 

## Modding Guide

Mods are stored as a series of XML files in roughly the same format as the game's library.

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


### ID Numbers

Most of the items in the game's library are identified by a numeric ID rather than a human-readable name.

If you want to replace an *existing* game definition, like the included Greenhouse mod does, simply copy that definition into to your mod with the same ID number that the game uses. The mod loader will replace the game's definition with the one from your mod.

If you want to create a *new* definition, things get a bit trickier because you need to make sure your ID numbers are unique across all mods that might get loaded. Luckily IDs can be any (positive) 32-bit integer which means there's lots of space.

I recommend prefixing your definition IDs with your Discord user number (e.g. mine is #4511) and a sequential mod number (e.g. I used `00` for the `artificial-plant` example, `01` for `exterior-air-vent`, etc) to come up with something reasonably unique, e.g. `451102000` for the Monster Meat crop recipe in the `greenhouse` example (and then `451102001` for the next ID in that mod, `451102002` for the one after that, etc etc).


### Navigating the Library

Since ID numbers are unique they're reasonably easy to follow in a text editor - if you find a definition that references another, simply search for the referenced ID that you're interested in.

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


### Textures and Animations

Extracting and annotating game assets also decodes and explodes the game's textures into `library/textures.exploded`. The game's original packed textures are written to `library/textures.exploded/*.png` and the texture regions are written to `library/textures.exploded/*/*.png`, where the folder name is the texture ID and the filename is the region ID.

Regions definitions can be found in `library/textures.xml` in `<re n="..." />` tags and are used in `library/animations.xml` by the `<assetPos a="..." />` tags.

The loader can overwrite existing textures from the base game and add new ones. To overwrite a texture, simply place a file called `123.png` in a directory called `textures` (where 123 is the id of the texture you want to replace). 

To add a new texture, you need to add a `<re n="..." t="..." />` entry in `library/textures.xml`. Textures are packed together in `.cim` files, which are defined in `<t i="..." />` entries. The `re` entry references the `t` entry through it's index `i`. Take care of choosing reasonably unique indexes to avoid conflicts. Once this is done, you can add the `123456.png` file to the `textures` directory. 

When loading your mod, the modloader will output the png version of the packed texture file for debugging purposes. This will allow you to check proper placement for new textures, or correct merging for existing ones.

