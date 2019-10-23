from __future__ import absolute_import
'''
Package contain all unit/integration tests for the `brian2` package.
'''
import os
import sys
from io import StringIO

from past.builtins import basestring

import brian2
from brian2.core.preferences import prefs
from brian2.devices.device import all_devices, set_device, reset_device

try:
    import nose
    from nose.plugins.errorclass import ErrorClassPlugin, ErrorClass
    import nose.plugins.doctests as doctests
    import doctest

    class NotImplementedPlugin(ErrorClassPlugin):
        enabled = True
        notimplemented = ErrorClass(NotImplementedError,
                                    label='NOT_IMPLEMENTED',
                                    isfailure=True)

        def configure(self, options, conf):
            # For some reason, this only works if this method exists...
            pass

    class NotImplementedNoFailurePlugin(ErrorClassPlugin):
        enabled = True
        notimplemented = ErrorClass(NotImplementedError,
                                    label='NOT_IMPLEMENTED',
                                    isfailure=False)

        def configure(self, options, conf):
            # For some reason, this only works if this method exists...
            pass

    class OurDoctestFinder(doctest.DocTestFinder):
        def _get_test(self, obj, name, module, globs, source_lines):
            if getattr(obj, '_do_not_run_doctests', False):
                return None
            # note that doctest.DocTestFinder is an old-style class in Python 2,
            # we therefore cannot use the super mechanism
            return doctest.DocTestFinder._get_test(self, obj, name, module,
                                                   globs, source_lines)

    class OurDoctestPlugin(doctests.Doctest):
        name = 'ourdoctest'
        enabled = True

        def configure(self, options, config):
            super(OurDoctestPlugin, self).configure(options, config)
            self.finder = OurDoctestFinder()

        def options(self, parser, env):
            pass  # do not register any options

except ImportError:
    nose = None


def clear_caches():
    from brian2.utils.logger import BrianLogger
    BrianLogger._log_messages.clear()
    from brian2.codegen.translation import make_statements
    make_statements._cache.clear()


def make_argv(dirnames, attributes):
    '''
    Create the list of arguments for the ``nosetests`` call.

    Parameters
    ----------
    dirnames : list of str
        The list of directory names to check for tests.
    attributes : str
        The attributes of the tests to include.

    Returns
    -------
    argv : list of str
        The arguments for `nose.main`.

    '''
    argv = (['nosetests'] + dirnames +
            ['-c=',  # no config file loading
             '-I', '^hears\.py$',
             '-I', '^\.',
             '-I', '^_',
             "-a", attributes,
             '--nologcapture',
             '--exe'])
    return argv


def run(codegen_targets=None, long_tests=False, test_codegen_independent=True,
        test_standalone=None, test_openmp=False,
        test_in_parallel=['codegen_independent', 'numpy', 'cython', 'cpp_standalone'],
        reset_preferences=True, fail_for_not_implemented=True,
        build_options=None, extra_test_dirs=None, float_dtype=None):
    '''
    Run brian's test suite. Needs an installation of the nose testing tool.

    For testing, the preferences will be reset to the default preferences.
    After testing, the user preferences will be restored.

    Parameters
    ----------
    codegen_targets : list of str or str
        A list of codegeneration targets or a single target, e.g.
        ``['numpy', 'weave']`` to test. The whole test suite will be repeatedly
        run with `codegen.target` set to the respective value. If not
        specified, all available code generation targets will be tested.
    long_tests : bool, optional
        Whether to run tests that take a long time. Defaults to ``False``.
    test_codegen_independent : bool, optional
        Whether to run tests that are independent of code generation. Defaults
        to ``True``.
    test_standalone : str, optional
        Whether to run tests for a standalone mode. Should be the name of a
        standalone mode (e.g. ``'cpp_standalone'``) and expects that a device
        of that name and an accordingly named "simple" device (e.g.
        ``'cpp_standalone_simple'`` exists that can be used for testing (see
        `CPPStandaloneSimpleDevice` for details. Defaults to ``None``, meaning
        that no standalone device is tested.
    test_openmp : bool, optional
        Whether to test standalone test with multiple threads and OpenMP. Will
        be ignored if ``cpp_standalone`` is not tested. Defaults to ``False``.
    reset_preferences : bool, optional
        Whether to reset all preferences to the default preferences before
        running the test suite. Defaults to ``True`` to get test results
        independent of the user's preference settings but can be switched off
        when the preferences are actually necessary to pass the tests (e.g. for
        device-specific settings).
    fail_for_not_implemented : bool, optional
        Whether to fail for tests raising a `NotImplementedError`. Defaults to
        ``True``, but can be switched off for devices known to not implement
        all of Brian's features.
    build_options : dict, optional
        Non-default build options that will be passed as arguments to the
        `set_device` call for the device specified in ``test_standalone``.
    extra_test_dirs : list of str or str, optional
        Additional directories as a list of strings (or a single directory as
        a string) that will be searched for additional tests.
    float_dtype : np.dtype, optional
        Set the dtype to use for floating point variables to a value different
        from the default `core.default_float_dtype` setting.
    '''
    if nose is None:
        raise ImportError('Running the test suite requires the "nose" package.')

    if build_options is None:
        build_options = {}

    if os.name == 'nt':
        test_in_parallel = []

    if extra_test_dirs is None:
        extra_test_dirs = []
    elif isinstance(extra_test_dirs, basestring):
        extra_test_dirs = [extra_test_dirs]

    multiprocess_arguments = ['--processes=-1',
                              '--process-timeout=3600',  # we don't want them to time out
                              '--process-restartworker']

    if codegen_targets is None:
        codegen_targets = ['numpy']
        try:
            import scipy.weave
            codegen_targets.append('weave')
        except ImportError:
            try:
                import weave
                codegen_targets.append('weave')
            except ImportError:
                pass
        try:
            import Cython
            codegen_targets.append('cython')
        except ImportError:
            pass
    elif isinstance(codegen_targets, basestring):  # allow to give a single target
        codegen_targets = [codegen_targets]

    dirname = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    dirnames = [dirname] + extra_test_dirs
    # We write to stderr since nose does all of its output on stderr as well
    sys.stderr.write('Running tests in %s ' % (', '.join(dirnames)))
    if codegen_targets:
        sys.stderr.write('for targets %s' % (', '.join(codegen_targets)))
    ex_in = 'including' if long_tests else 'excluding'
    sys.stderr.write(' (%s long tests)\n' % ex_in)

    sys.stderr.write("Running Brian version {} "
                     "from '{}'\n".format(brian2.__version__,
                                          os.path.dirname(brian2.__file__)))

    all_targets = set(codegen_targets)

    if test_standalone:
        if not isinstance(test_standalone, basestring):
            raise ValueError('test_standalone argument has to be the name of a '
                             'standalone device (e.g. "cpp_standalone")')
        if test_standalone not in all_devices:
            raise ValueError('test_standalone argument "%s" is not a known '
                             'device. Known devices are: '
                             '%s' % (test_standalone,
                                     ', '.join(repr(d) for d in all_devices)))
        sys.stderr.write('Testing standalone \n')
        all_targets.add(test_standalone)
    if test_codegen_independent:
        sys.stderr.write('Testing codegen-independent code \n')
        all_targets.add('codegen_independent')

    parallel_tests = all_targets.intersection(set(test_in_parallel))
    if parallel_tests:
        sys.stderr.write('Testing with multiple processes for %s\n' % ', '.join(parallel_tests))

    if reset_preferences:
        sys.stderr.write('Resetting to default preferences\n')

    if reset_preferences:
        # Store the currently set preferences and reset to default preferences
        stored_prefs = prefs.as_file
        prefs.read_preference_file(StringIO(prefs.defaults_as_file))

    # Avoid failures in the tests for user-registered units
    import copy
    import brian2.units.fundamentalunits as fundamentalunits
    old_unit_registry = copy.copy(fundamentalunits.user_unit_register)
    fundamentalunits.user_unit_register = fundamentalunits.UnitRegistry()

    if float_dtype is not None:
        sys.stderr.write('Setting dtype for floating point variables to: '
                         '{}\n'.format(float_dtype.__name__))
        prefs['core.default_float_dtype'] = float_dtype
    prefs._backup()

    sys.stderr.write('\n')

    # Suppress INFO log messages during testing
    from brian2.utils.logger import BrianLogger, LOG_LEVELS
    log_level = BrianLogger.console_handler.level
    BrianLogger.console_handler.setLevel(LOG_LEVELS['WARNING'])

    # Switch off code optimization to get faster compilation times
    prefs['codegen.cpp.extra_compile_args_gcc'].extend(['-w', '-O0'])
    prefs['codegen.cpp.extra_compile_args_msvc'].extend(['/Od'])

    if fail_for_not_implemented:
        not_implemented_plugin = NotImplementedPlugin
    else:
        not_implemented_plugin = NotImplementedNoFailurePlugin
    # This hack is needed to get the NotImplementedPlugin working for multiprocessing
    import nose.plugins.multiprocess as multiprocess
    multiprocess._instantiate_plugins = [not_implemented_plugin]

    plugins = [not_implemented_plugin()]

    from brian2.devices import set_device
    set_device('runtime')
    try:
        success = []
        if test_codegen_independent:
            sys.stderr.write('Running tests that do not use code generation\n')
            # Some doctests do actually use code generation, use numpy for that
            prefs.codegen.target = 'numpy'
            prefs._backup()
            # Print output changed in numpy 1.14, stick with the old format to
            # avoid doctest failures
            import numpy as np
            try:
                np.set_printoptions(legacy='1.13')
            except TypeError:
                pass  # using a numpy version < 1.14
            argv = make_argv(dirnames, "codegen-independent")
            if 'codegen_independent' in test_in_parallel:
                argv.extend(multiprocess_arguments)
                multiprocess._instantiate_plugins.append(OurDoctestPlugin)
            success.append(nose.run(argv=argv,
                                    addplugins=plugins+[OurDoctestPlugin()]))
            if 'codegen_independent' in test_in_parallel:
                multiprocess._instantiate_plugins.remove(OurDoctestPlugin)
            clear_caches()

        for target in codegen_targets:
            sys.stderr.write('Running tests for target %s:\n' % target)
            prefs.codegen.target = target
            # Also set the target for string-expressions -- otherwise we'd only
            # ever test numpy for those
            prefs.codegen.string_expression_target = target
            prefs._backup()
            exclude_str = "!standalone-only,!codegen-independent"
            if not long_tests:
                exclude_str += ',!long'
            # explicitly ignore the brian2.hears file for testing, otherwise the
            # doctest search will import it, failing on Python 3
            argv = make_argv(dirnames, exclude_str)
            if target in test_in_parallel:
                argv.extend(multiprocess_arguments)
            success.append(nose.run(argv=argv,
                                    addplugins=plugins))
            clear_caches()

        if test_standalone:
            from brian2.devices.device import get_device, set_device
            set_device(test_standalone, directory=None,  # use temp directory
                       with_output=False, **build_options)
            sys.stderr.write('Testing standalone device "%s"\n' % test_standalone)
            sys.stderr.write('Running standalone-compatible standard tests (single run statement)\n')
            exclude_str = ',!long' if not long_tests else ''
            exclude_str += ',!multiple-runs'
            argv = make_argv(dirnames, 'standalone-compatible'+exclude_str)
            if test_standalone in test_in_parallel:
                argv.extend(multiprocess_arguments)
            success.append(nose.run(argv=argv,
                                    addplugins=plugins))
            clear_caches()

            reset_device()

            sys.stderr.write('Running standalone-compatible standard tests (multiple run statements)\n')
            set_device(test_standalone, directory=None,  # use temp directory
                       with_output=False, build_on_run=False, **build_options)
            exclude_str = ',!long' if not long_tests else ''
            exclude_str += ',multiple-runs'
            argv = make_argv(dirnames, 'standalone-compatible'+exclude_str)
            if test_standalone in test_in_parallel:
                argv.extend(multiprocess_arguments)
            success.append(nose.run(argv=argv,
                                    addplugins=plugins))
            clear_caches()
            reset_device()

            if test_openmp and test_standalone == 'cpp_standalone':
                # Run all the standalone compatible tests again with 4 threads
                set_device(test_standalone, directory=None, # use temp directory
                           with_output=False, **build_options)
                prefs.devices.cpp_standalone.openmp_threads = 4
                prefs._backup()
                sys.stderr.write('Running standalone-compatible standard tests with OpenMP (single run statements)\n')
                exclude_str = ',!long' if not long_tests else ''
                exclude_str += ',!multiple-runs'
                argv = make_argv(dirnames,
                                 'standalone-compatible' + exclude_str)
                success.append(nose.run(argv=argv,
                                        addplugins=plugins))
                clear_caches()
                reset_device()

                set_device(test_standalone, directory=None, # use temp directory
                           with_output=False, build_on_run=False, **build_options)
                sys.stderr.write('Running standalone-compatible standard tests with OpenMP (multiple run statements)\n')
                exclude_str = ',!long' if not long_tests else ''
                exclude_str += ',multiple-runs'
                argv = make_argv(dirnames,
                                 'standalone-compatible' + exclude_str)
                success.append(nose.run(argv=argv,
                                        addplugins=plugins))
                clear_caches()
                prefs.devices.cpp_standalone.openmp_threads = 0
                prefs._backup()

                reset_device()

            sys.stderr.write('Running standalone-specific tests\n')
            exclude_openmp = ',!openmp' if not test_openmp else ''
            argv = make_argv(dirnames, test_standalone+exclude_openmp)
            if test_standalone in test_in_parallel:
                argv.extend(multiprocess_arguments)
            success.append(nose.run(argv=argv,
                                    addplugins=plugins))
            clear_caches()

        all_success = all(success)
        if not all_success:
            sys.stderr.write(('ERROR: %d/%d test suite(s) did not complete '
                              'successfully (see above).\n') % (len(success) - sum(success),
                                                                len(success)))
        else:
            sys.stderr.write(('OK: %d/%d test suite(s) did complete '
                              'successfully.\n') % (len(success), len(success)))
        return all_success

    finally:
        BrianLogger.console_handler.setLevel(log_level)

        if reset_preferences:
            # Restore the user preferences
            prefs.read_preference_file(StringIO(stored_prefs))
            prefs._backup()

        fundamentalunits.user_unit_register = old_unit_registry


if __name__ == '__main__':
    run()
