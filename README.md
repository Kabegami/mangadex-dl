This repo is a fork of https://github.com/frozenpandaman/mangadex-dl adapted to use async programming to drasticly
improve download speed.
It downloads mangas from [MangaDex.org](https://mangadex.org/), please make sure to check their website 
and thanks them :)

# Installation

It requires [Python 3.5+] (https://www.python.org/downloads/)

```
$ git clone https://github.com/Kabegami/mangadex-dl
$ pip install -r requirements
$ cd mangadex-dl/
$ python mangadex-dl.py URL
```

# Optional flags

* `-l`: Download releases in a language other than English. For a list of language codes, see the [wiki page](https://github.com/frozenpandaman/mangadex-dl/wiki/language-codes). (accept a list seperated by comma)
* `--cbz`: Package downloaded chapters into .cbz ([comic book archive](https://en.wikipedia.org/wiki/Comic_book_archive)) files.
* `-o`: Use a custom output directory name to save downloaded chapters. Defaults to "download".
* `--configure` : Open the configuration file to save new defaults values for the options
* `-c, --chapters` : A list separated by comma, of chapter number or range (start-end) ex : 1,3,4-10 by default select all chapters

# License

[GPLv3](https://www.gnu.org/licenses/gpl-3.0.html)