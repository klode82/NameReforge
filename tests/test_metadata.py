import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from nameforge.core.actions import FileContext, NameParts
from nameforge.core.metadata import AudioTags, DateTime, ExifTags, RegexReplace


def run(action, path, index=0):
    path = Path(path)
    return action.process(NameParts.from_name(path.name), FileContext(path, index, index)).full


def test_regex_groups_and_flags():
    assert run(RegexReplace(r"(\d+)-(\w+)", r"\2_\1"), "/d/12-ab.t") == "ab_12.t"
    assert run(RegexReplace(r"(?P<n>\d+)", r"[\g<n>]"), "/d/a12.t") == "a[12].t"
    assert run(RegexReplace("ABC", "x", ignore_case=True), "/d/abc.t") == "x.t"
    assert run(RegexReplace(r"\.t$", "", target="full"), "/d/abc.t") == "abc"
    assert run(RegexReplace(r"\.t$", ""), "/d/abc.t") == "abc.t"  # stem: l'estensione non è toccata
    assert run(RegexReplace(""), "/d/abc.t") == "abc.t"


def test_regex_invalid():
    import re

    with pytest.raises(re.error):
        RegexReplace("(")
    with pytest.raises(re.error):
        RegexReplace("a", r"\1")


def test_datetime(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("")
    import os

    os.utime(f, (0, 1_700_000_000))  # 2023-11-14 (UTC)
    assert run(DateTime("modified", "%Y"), f) == "2023_a.txt"
    assert run(DateTime("modified", "%Y", position="replace"), f) == "2023.txt"
    assert run(DateTime(), tmp_path / "missing.txt") == "missing.txt"
    assert DateTime("created").warning(1) is None or "Linux" in DateTime("created").warning(1)


def make_jpg(path, with_exif=True):
    img = Image.new("RGB", (40, 30))
    if with_exif:
        exif = img.getexif()
        exif[0x010F] = "Canon "
        exif[0x0110] = "EOS 5D"
        exif.get_ifd(0x8769)[0x9003] = "2021:05:04 10:20:30"
        img.save(path, exif=exif)
    else:
        img.save(path)
    return path


def test_exif(tmp_path):
    a = make_jpg(tmp_path / "a.jpg")
    assert run(ExifTags(), a) == "2021-05-04_102030.jpg"
    assert run(ExifTags("{make}-{model}-{width}x{height}"), a) == "Canon-EOS 5D-40x30.jpg"
    assert run(ExifTags("{date:%Y}", position="prefix", separator="_"), a) == "2021_a.jpg"


def test_exif_missing(tmp_path):
    b = make_jpg(tmp_path / "b.jpg", with_exif=False)
    assert run(ExifTags(), b) == "b.jpg"  # senza dati: invariato
    assert run(ExifTags("{make}", skip_if_missing=False, missing="ND"), b) == "ND.jpg"
    assert run(ExifTags("{date:%Y}", skip_if_missing=False, missing="ND"), b) == "b.jpg"  # formato incompatibile
    txt = tmp_path / "c.txt"
    txt.write_text("not an image")
    assert run(ExifTags(), txt) == "c.txt"


def test_template_validation():
    with pytest.raises(ValueError, match="sconosciuto"):
        ExifTags("{colore}")
    with pytest.raises(ValueError):
        AudioTags("{artist")


@pytest.fixture
def tagged(tmp_path):
    ff = shutil.which("ffmpeg")
    if not ff:
        pytest.skip("ffmpeg non disponibile")
    out = {}
    for ext, codec in (("mp3", "libmp3lame"), ("flac", "flac"), ("ogg", "libvorbis"), ("opus", "libopus"), ("m4a", "aac")):
        p = tmp_path / f"in.{ext}"
        cmd = [ff, "-v", "error", "-f", "lavfi", "-i", "sine=duration=0.3", "-c:a", codec,
               "-metadata", "artist=Ada", "-metadata", "title=Song", "-metadata", "track=3/12",
               "-metadata", "date=1999-05-01", "-y", str(p)]
        if subprocess.run(cmd, check=False).returncode == 0:
            out[ext] = p
    return out


def test_audio_formats(tagged):
    assert tagged, "nessun formato generato"
    for ext, p in tagged.items():
        assert run(AudioTags("{artist} - {title} {track:02} {year}"), p) == f"Ada - Song 03 1999.{ext}", ext


def test_audio_missing(tmp_path):
    f = tmp_path / "x.mp3"
    f.write_bytes(b"\xff\xfb\x90\x00" + bytes(413) * 4)
    assert run(AudioTags(), f) == "x.mp3"
    assert run(AudioTags(skip_if_missing=False, missing="?"), f) == "? - ?.mp3"


def test_regex_dollar_syntax_equals_backslash():
    pat = r"(\d)x(\d{2}) - (?P<t>\w+)"
    for repl in (r"S0\1E\2 \3", "S0$1E$2 $3", "S0${1}E${2} ${t}", r"S0\1E$2 \g<t>"):
        assert run(RegexReplace(pat, repl), "/d/2x01 - Pilot.t") == "S02E01 Pilot.t", repl


def test_regex_dollar_edge_cases():
    assert run(RegexReplace(r"(a)", "$$1"), "/d/a.t") == "$1.t"  # $$ = dollaro vero
    assert run(RegexReplace(r"(a)", "US$ 5 $1"), "/d/a.t") == "US$ 5 a.t"  # $ senza cifra: letterale
    assert run(RegexReplace(r"(a)", "$12"), "/d/a.t") == "a2.t"  # un solo gruppo: $1 seguito da "2"
    assert run(RegexReplace(r"a", "[$0]"), "/d/a.t") == "[a].t"  # $0 = tutto il trovato


def test_regex_dollar_unknown_group_is_an_error():
    import re

    with pytest.raises(re.error):
        RegexReplace(r"(a)", "$5")
    with pytest.raises(re.error):
        RegexReplace(r"(a)", "${nome}")


def test_regex_unknown_named_group_is_a_regular_error(qtbot):
    import re

    from nameforge.actionpanels import SPECS
    from nameforge.mainwindow import MainWindow

    with pytest.raises(re.error):
        RegexReplace("(a)", r"\g<nome>")
    win = MainWindow()
    qtbot.addWidget(win)
    tab = win.actions_tab
    row = [s.key for s in SPECS].index("regex")
    tab.list.setCurrentRow(row)
    tab.panels[row]._widgets["pattern"].setText("(a)")
    tab.panels[row]._widgets["replacement"].setText("${nome}")
    tab.current_actions()  # prima: IndexError non gestito
    assert tab.panels[row].error and "gruppo" in tab.panels[row].error
