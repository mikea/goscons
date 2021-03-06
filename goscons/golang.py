from goscanner import GoScanner
import SCons.Errors
import os
import platform
import re

def find_package(env, pkg, path):
    pkgfile = env.subst(os.path.join(*pkg.split('/'))+'$GOLIBSUFFIX')
    return env.FindFile(pkgfile, path)

def godep(env, dep, sconscript='SConstruct', build=True, *args, **kw):
    if dep in env['GODEPS']: return
    env.AppendUnique(GODEPS=dep)
    depdir = env.Dir(os.path.join('#..',dep))
    pkgdir = env.Dir(os.path.join(str(depdir),'pkg','${GOOS}_${GOARCH}'))
    bindir = env.Dir(os.path.join(str(depdir),'bin','${GOOS}_${GOARCH}'))
    if build:
        sconscriptfile = depdir.File(sconscript)
        env.SConscript(sconscriptfile, exports={'GODEP_BUILD' : True})
    else:
        env.AppendUnique(GODEPPKGPATH=pkgdir)
        env.AppendUnique(GODEPRPATH=pkgdir)
    if not depdir.isdir():
        raise SCons.Errors.UserError, 'Missing dependency: %s' % dep
    return [pkgdir, bindir]

# TODO add $GOROOT/bin to PATH automatically?
def generate(env):
    try:
        env.Import('GODEP_BUILD')
        env['GODEP_BUILD'] = True
    except SCons.Errors.UserError:
        env['GODEP_BUILD'] = False

    if 'GOROOT' not in env:
        if 'GOROOT' not in os.environ:
            raise SCons.Errors.UserError, 'Set GOROOT in your environment'
        env['GOROOT'] = os.environ['GOROOT']

    if 'GOOS' not in env:
        if platform.system() == 'Linux':
            env['GOOS'] = 'linux'
        elif platform.system() == 'Darwin':
            env['GOOS'] = 'darwin'
        elif platform.system() == 'Windows':
            env['GOOS'] = 'windows'
        else:
            raise SCons.Errors.InternalError, \
                'Unsupported platform: %s' % platform.system()

    if 'GOARCH' not in env:
        if 'GOARCH' in os.environ:
            env['GOARCH'] = os.environ['GOARCH']
        else:
            # TODO use sysctl machdep.cpu.extfeatures on darwin
            if platform.machine() == 'x86_64':
                env['GOARCH'] = 'amd64'
            elif re.match('i\d86', platform.machine()):
                env['GOARCH'] = '386'
            else:
                raise SCons.Errors.InternalError, \
                    'Unsupported arch: %s' % platform.machine()

    # TODO don't call Dir here, because it causes premature
    # substitution of the environment
    env['GOROOTBINPATH'] = env.Dir('$GOROOT/bin')
    env['GOPROJBINPATH'] = env.Dir('#bin/${GOOS}_$GOARCH')
    env['GOROOTPKGPATH'] = env.Dir('$GOROOT/pkg/${GOOS}_$GOARCH')
    env['GOPROJPKGPATH'] = env.Dir('#pkg/${GOOS}_$GOARCH')

    env['GOPKGPATH'] = ['$GOPROJPKGPATH', '$GODEPPKGPATH', '$GOROOTPKGPATH']
    env['GOSCONSHELPER'] = 'goscons-helper'
    env['GOFILESUFFIX'] = '.go'

    tools = [
        'gopkg',
        'gocmd',
        'cgo',
        'goc',
        'golink',
        'plan9c',
        'plan9a',
        'gopack',
        'gotest'
        ]
    if env['GOARCH'] == 'amd64':
        tools += ['goc6','golink6','plan9c6','plan9a6']
    elif env['GOARCH'] == '386':
        tools += ['goc8','golink8','plan9c8','plan9a8']
    else:
        raise SCons.Errors.InternalError, \
            'Unsupported GOARCH: %s' % env['GOARCH']

    for t in SCons.Tool.FindAllTools(tools,env):
        SCons.Tool.Tool(t)(env)

    env.AddMethod(find_package, 'FindGoPackage')

    env['GODEPS'] = []
    env['GODEPPKGPATH'] = []
    env['GODEPRPATH'] = []
    env.AddMethod(godep, 'GoDep')

    SCons.Tool.SourceFileScanner.add_scanner('.go', GoScanner)

    env.Alias('goinstall')
    env.Alias('test')
    env.Alias('bench')

    if not env['GODEP_BUILD']:
        gofmt_cmd = "find ${TOP.abspath} -name '*.go' | xargs gofmt -s=true -w=true"
        env.AlwaysBuild(env.Alias('gofmt', [], gofmt_cmd, TOP=env.Dir('#')))
        nuke_cmds = [
            "find ${TOP.abspath} -name '*.[568aovq]' | xargs rm -f",
            "find ${TOP.abspath} -name '_testmain.go' | xargs rm -f",
            "find ${TOP.abspath} -name '_obj' -type d | xargs rm -rf",
            "find ${TOP.abspath} -name '_test' -type d | xargs rm -rf",
            "find ${TOP.abspath} -name '_cgo_*.*' | xargs rm -f",
            "find ${TOP.abspath} -name '*.cgo[12].*' | xargs rm -f",
            "rm -rf ${TOP.abspath}/bin",
            "rm -rf ${TOP.abspath}/pkg"
            ]
        env.AlwaysBuild(env.Alias('nuke', [], nuke_cmds, TOP=env.Dir('#')))

    env['GOTESTRUNNER'] = ''

def exists(env):
    return 1
