"""Real JVM/AspectJ regression. Set SHL_TEST_JAVA{25,27} and SHL_TEST_WEAVER."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from ui import launch_config
from ui.database import JarMod
from ui.gameinfo import GameInfo

SOURCE = r"""
package fi.bugbyte.spacehaven.gui.menu;
import java.text.DateFormat;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
public class GameMenu {
    static DateFormat formatter() {
        return new SimpleDateFormat("h:mm:ss\u202fa'\u00a0X'", Locale.ROOT);
    }
    static class SaveGameSlot {
        String actual;
        void toggleExpand() { actual = formatter().format(new Date(0L)); }
        String control() { return formatter().format(new Date(0L)); }
    }
    static class CloudTab1 {
        static class CloudSlot {
            String actual;
            void setInfo(Date date) { actual = formatter().format(date); }
        }
    }
    static boolean changed(String value) {
        return value.indexOf('\u202f') < 0 && value.indexOf('\u00a0') < 0 && value.endsWith(" X");
    }
    public static void main(String[] args) {
        SaveGameSlot local = new SaveGameSlot();
        local.toggleExpand();
        CloudTab1.CloudSlot cloud = new CloudTab1.CloudSlot();
        cloud.setInfo(new Date(0));
        if (!changed(local.actual) || !changed(cloud.actual) || changed(local.control()))
            throw new AssertionError("DateFix call-site scope is incorrect");
        System.out.println("DATEFIX_WEAVING_OK");
    }
}
"""


class WeavingSmokeTests(unittest.TestCase):
    def smoke(self, major):
        java = os.environ.get(f"SHL_TEST_JAVA{major}")
        weaver = os.environ.get("SHL_TEST_WEAVER")
        javac = shutil.which("javac")
        if not (java and weaver and javac):
            self.skipTest(f"Requires SHL_TEST_JAVA{major}, SHL_TEST_WEAVER and javac")
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = Path(tmp).resolve()
            src = game_dir / "GameMenu.java"
            src.write_text(SOURCE, encoding="utf-8")
            subprocess.run([javac, "--release", "8", "-Xlint:-options", "-d", str(game_dir), str(src)], check=True, timeout=30)
            game_jar = game_dir / "spacehaven.jar"
            with ZipFile(game_jar, "w") as jar:
                jar.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\nMain-Class: fi.bugbyte.spacehaven.gui.menu.GameMenu\n")
                jar.writestr("version.txt", "1.0.4")
                for class_file in game_dir.rglob("*.class"):
                    jar.write(class_file, class_file.relative_to(game_dir).as_posix())

            mod_dir = game_dir / "mods" / "Example"
            mod_dir.mkdir(parents=True)
            info = mod_dir / "info.xml"
            info.write_text("<mod><name>Example</name></mod>", encoding="utf-8")
            mod = JarMod(info, GameInfo(game_jar), "example.jar")
            cases = (
                ("clean filtered launch", None),
                ("launch with a restricted mod", "<weaver><include within='example..*'/></weaver>"),
                ("launch with an unrestricted mod", "<weaver/>"),
            )
            for name, descriptor in cases:
                with self.subTest(major=major, launch=name):
                    mods = []
                    if descriptor is not None:
                        with ZipFile(mod.jarPath, "w") as jar:
                            jar.writestr("META-INF/aop.xml", f"<aspectj>{descriptor}</aspectj>")
                        mods = [mod]
                    with patch.object(launch_config.aspectj_runtime, "installed_aspectj", return_value=Path(weaver)):
                        command, env = launch_config.build(game_dir / "spacehaven.exe", game_jar, mods, java, major)
                    result = subprocess.run(command, cwd=game_dir, env=env, capture_output=True, text=True, timeout=30)
                    self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                    self.assertIn("DATEFIX_WEAVING_OK", result.stdout)

    def test_java25(self):
        self.smoke(25)

    def test_java27(self):
        self.smoke(27)
