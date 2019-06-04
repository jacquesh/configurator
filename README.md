# Configurator

A simple tool for substituting configuration values into template files, with a focus on ease-of-use. Originally written for my own benefit in 2017 while working at SMSPortal, made available here with permission.

While the source is in python, [Nuitka](http://nuitka.net/) is used to compile it into a set of binaries that do not require python to be installed.

Source and changes are in configurator.py (which is also included in binary distributions).

## Usage
You need a template file, which is any file named "app.config", "web.config" or "appsettings.json" (the names are easily changed at the top of the source file) containing template variables delimited by %'s (the same way that Windows environment variables are, for example: %MYVAR%).
You also need one or more value files, which are files of the form "<environment-name>.<template-file-name>" (for example "dev.app.config" or "prod.appsettings.json"). These are similarly easily changed at the top of the file.
You then simply point the tool at these two files (either explicitly by giving them as arguments, or by letting it walk the current directory tree and find them itself) and it will substitute all the template variables in the template file with the values in the value file.
