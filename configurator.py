import argparse
import os.path
import sys

version = "2019-03-14"
"""
CHANGELOG:
2019-03-14:
- Add the -w "whatif" flag which tells the application to do a dryrun, which will print out the replacements but does not actually do them
- Allow the user to specify any file as the template (using the '-t' flag) as long as its contents can be used as a template file.
    - This is primarily useful if you want to apply config to a precompiled .NET Framework application, where the config file's name has been changed from App.config.

2019-02-26:
- Add the default to the documentation for the --dir flag
- Add an output log for any file that was found as a potential template file but that contained no variables to be substituted (and was therefore ignored)

2018-03-20:
- Terminate the process with exitcode 1 rather than 0 when an error is encountered

2018-03-19:
- Add a verbose output flag that lets you turn on extra warnings
- Add a check for duplicate value specifications when a value is specified more than once in the selected value files.
    - An example of this is where you specify a value in prod and then in qa or dev config (with default environment specifications).
    - These warnings are only printed in verbose mode so that we do not get very large output for files that are not trying to be hierarchial (as is historically the case)
- Remove "bin" from the ignored directory list and instead add "Debug" and "Release"
    - "bin" is a far more commonly used directory name and so Debug and Release are used to achieve the same exclusion of build directories in development,
       while not excluding a directory that might be used in live environments.

2018-03-12:
- Fixed the 'conf' bash script not passing in any provided arguments to the executable
- Add a rule to ignore any directory that has a specific name when searching for template or value files.
    - Currently ignored directory names are: ".git", "bin", "obj", "packages", ".vs", ".idea"

2018-03-08:
- Slightly improved the clarity of some error messages.
- Consider 'appsettings.json' to be a valid template file name.
- Automatic value-file selection now takes the file for the selected environment that is closest in the file tree to the template file (rather than the first one it finds while searching).
- Now supports storing config as diffs rather than complete sets of values.
    - This means that specifying the environment of 'dev' will apply the dev, qa and prod config, whereas 'qa' will apply qa and prod, and 'prod' will apply only prod config.
    - This can be disabled (causing only the first of the matching value files to be used) with the new --single-env flag.
    - In interactive mode, multiple configs are applied by providing a comma-separated list of environments. Values are applied in the order in which they are supplied.

2017-11-24:
- Correctly filter the list of value files to "*.app.config" or "*.web.config", ignoring other "App.config" files.
"""

templateFilePatterns = ["app.config", "web.config", "appsettings.json"]
environmentNames = ["dev", "qa", "prod"]
verbose = False

class TemplateFileStatus:
    NONE = 0
    NO_VARIABLES = 1
    TEMPLATE = 2

class TemplateValueMapping(object):
    def __init__(self):
        self.map = {}
        self.title = "Untitled Mapping"

    def __getitem__(self, key):
        return self.map[key]

    def __setitem__(self, key, value):
        self.map[key] = value

    def __contains__(self, key):
        return key in self.map

    def __iter__(self):
        return self.map.__iter__()

    def keys(self):
        return self.map.keys()

    def values(self):
        return self.map.values()

def ContainsTemplateVariables(filepath):
    with open(filepath, "r") as potentialFile:
        potentialContents = potentialFile.read()
        if potentialContents.count("%") >= 2: # We need 2 since a single % cannot delimit a variable name
            return True
    return False

def isTemplateFile(filepath):
    if os.path.basename(filepath.lower()) not in templateFilePatterns:
        return TemplateFileStatus.NONE
    if ContainsTemplateVariables(filepath):
        return TemplateFileStatus.TEMPLATE
    return TemplateFileStatus.NO_VARIABLES

def isValueFile(filepath):
    for pattern in templateFilePatterns:
        filename = os.path.basename(filepath).lower()
        if filename.endswith("."+pattern):
            return True
    return False

def populateTemplate(templateFilename, valueMapping, dryrun):
    print "Populating [%s] with values from [%s]" % (templateFilename, valueMapping.title)
    with open(templateFilename, "r") as templateFile:
        templateContents = templateFile.read()
    for key in valueMapping:
        for templateVariable in ("%%%%%s%%%%" % key, "%%%s%%" % key):
            searchStart = 0
            while True:
                foundIndex = templateContents.find(templateVariable, searchStart)
                if foundIndex < 0:
                    break
                if verbose or dryrun:
                    lineNo = templateContents[:foundIndex].count('\n') + 1
                    print "Replace \'%s\' with \'%s\' on line %d" % (templateVariable, valueMapping[key], lineNo)
                beforeChunk = templateContents[:foundIndex]
                afterChunk = templateContents[foundIndex + len(templateVariable):]
                templateContents = beforeChunk + valueMapping[key] + afterChunk
                searchStart = foundIndex + len(valueMapping[key])
    if not dryrun:
        with open(templateFilename, "w") as templateFile:
            templateFile.write(templateContents)

def loadValueFile(valueFilename):
    result = TemplateValueMapping()
    result.title = os.path.basename(valueFilename)
    with open(valueFilename, "r") as valueFile:
        for valueLine in valueFile:
            valueLine = valueLine.strip()
            if len(valueLine) == 0:
                continue
            keyValueSplitIndex = valueLine.find("=")
            valueKey = valueLine[:keyValueSplitIndex]
            valueValue = valueLine[keyValueSplitIndex+1:]
            result[valueKey] = valueValue
    return result

def mergeValueMappings(valueMappings):
    if len(valueMappings) == 0:
        return {}
    errors = ""
    result = valueMappings[0]
    previousTitle = valueMappings[0].title
    for mapping in valueMappings[1:]:
        result.title += " -> %s" % mapping.title
        for key in mapping:
            if key not in result:
                result[key] = mapping[key]
            else:
                if result[key] == mapping[key]:
                    errors += "Redundant specification of %s (\'%s\') in %s\n" % (key, result[key], previousTitle)
        previousTitle = mapping.title
    if verbose and len(errors) > 0:
        print "\n%s" % errors
    return result

def getDistanceBetweenPaths(A, B):
    pathA = os.path.realpath(A)
    pathB = os.path.realpath(B)
    aTokens = [t for split in pathA.split('/') for t in split.split('\\')]
    bTokens = [t for split in pathB.split('/') for t in split.split('\\')]
    lastMatchIndex = 0
    while (lastMatchIndex < len(aTokens)) and \
            (lastMatchIndex < len(bTokens)) and \
            (aTokens[lastMatchIndex].lower() == bTokens[lastMatchIndex].lower()):
        lastMatchIndex += 1
    return (len(aTokens) - lastMatchIndex) + (len(bTokens) - lastMatchIndex)

def run():
    print "Configurator version: %s" % version
    parser = argparse.ArgumentParser(description='Automatically fill out templated config files')
    parser.add_argument('-d', '--dir', help='the directory to recursively search for files. Defaults to the current working directory', default=os.getcwd())
    parser.add_argument('-e', '--env', help='the name of the environment whose values you want. Defaults to \'dev\'', default='dev')
    parser.add_argument('-t', '--template', help='the path to the template file to populate')
    parser.add_argument('-s', '--single-env', dest='singleEnv', action='store_true', help='force the application of only one environment config (rather than applying environments hierarchially)')
    parser.add_argument('-i', '--interactive', dest='interactive', action='store_true', help='interactive mode, all available options will be presented for you to choose from')
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', help='print verbose output')
    parser.add_argument('-w', '--whatif', dest='whatif', action='store_true', help='print details of what would happen if the same command was run without the whatif flag')
    args = parser.parse_args()

    global verbose
    verbose = args.verbose

    if not args.dir:
        rootdir = os.getcwd()
    else:
        rootdir = args.dir
    print "Searching in: %s" % rootdir

    templateFileOptions = []
    valueFileOptions = []

    ignoredDirnames = [".git", "Debug", "Release", "obj", "packages", ".vs", ".idea"]
    for dirpath, dirnames, filenames in os.walk(rootdir):
        dirsToRemove = [d for d in ignoredDirnames if d in dirnames]
        for d in dirsToRemove:
            dirnames.remove(d)
        for f in filenames:
            filepath = os.path.join(dirpath, f)
            if isValueFile(filepath):
                valueFileOptions.append(filepath)

            templateStatus = isTemplateFile(filepath)
            if templateStatus == TemplateFileStatus.TEMPLATE:
                templateFileOptions.append(filepath)
            elif templateStatus == TemplateFileStatus.NO_VARIABLES:
                print "File \'%s\' could be a template file but contains no substitutable variables" % filepath

    if (len(templateFileOptions) == 0) and (args.template is None):
        print "No valid template files (with the default naming scheme) found!"
        return False
    if len(valueFileOptions) == 0:
        print "No value files found!"
        return False

    if args.template:
        if not os.path.isfile(args.template):
            print "Unable to find the file \'%s\' to use as a template!" % args.template
            return False
        if not ContainsTemplateVariables(args.template):
            print "File \'%s\' does not contain any template variables and is therefore not a valid template file!" % args.template
            return False
        templateFilename = args.template
    elif len(templateFileOptions) == 1:
        templateFilename = templateFileOptions[0]
    elif args.interactive:
        print "Template files:"
        for index, template in enumerate(templateFileOptions):
            print "\t%d) %s" % (index+1, template)
        templateIndex = int(input("Select the template file to use:\n"))-1
        templateFilename = templateFileOptions[templateIndex]
    else:
        print "No template file specified and multiple templates available. Try again in interactive mode."
        return False
    print "Using template file: %s" % templateFilename

    if args.interactive:
        print "Value files:"
        for index, value in enumerate(valueFileOptions):
            print "\t%d) %s" % (index+1, value)
        valueIndexStr = raw_input("Select the value file to use (use a comma-separated list of indices to select multiple files):\n")
        valueIndices = [int(x)-1 for x in valueIndexStr.split(',')]
        valueFilenames = [valueFileOptions[i] for i in valueIndices]
    else:
        nearbyValueFiles = []
        minValueFileDistance = 1000
        for option in valueFileOptions:
            distance = getDistanceBetweenPaths(templateFilename, option)
            if distance < minValueFileDistance:
                minValueFileDistance = distance
                nearbyValueFiles = [option]
            elif distance == minValueFileDistance:
                nearbyValueFiles.append(option)

        if (args.env not in environmentNames) or (args.singleEnv):
            valueFilenames = [f for f in nearbyValueFiles if os.path.basename(f).startswith(args.env)]
            if len(valueFilenames) == 0:
                print "No value file for environment '%s' found!" % args.env
                return False
            if len(valueFilenames) > 1:
                print "Multiple matching value files were found (%s) for environment %s. Try again in interactive mode." % (", ".join(valueFilenames), args.env)
                return False
            valueFilenames = valueFilenames[:1]
        else:
            valueFilenames = []
            requestedEnvIndex = environmentNames.index(args.env)
            for env in environmentNames[requestedEnvIndex:]:
                envValueFiles = [f for f in nearbyValueFiles if os.path.basename(f).startswith(env)]
                if len(envValueFiles) > 1:
                    print "Multiple matching value files were found (%s) for environment %s. Try again in interactive mode." % (", ".join(envValueFiles), env)
                    return False
                elif len(envValueFiles) == 1:
                    valueFilenames.append(envValueFiles[0])

    valueMappings = []
    for valueFilename in valueFilenames:
        print "Loading value file %s" % valueFilename
        valueMappings.append(loadValueFile(valueFilename))

    mergedMapping = mergeValueMappings(valueMappings)
    populateTemplate(templateFilename, mergedMapping, args.whatif)
    print "Done"
    return True

if __name__ == "__main__":
    if not run():
        sys.exit(1)
