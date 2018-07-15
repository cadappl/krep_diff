
import os


def _dict_merge(ret, dictb):
  for key, value in dictb.items():
    if key not in ret:
      ret[key] = value

  return ret


class _FileBundle(object):
  FILE_HTML = 'html'
  FILE_TEXT = 'txt'

  def __init__(self, bundles):
    self.fbundles = dict()

    for key, filename in bundles.items():
      self.fbundles[key] = open(filename, 'w')

  def close(self):
    for _, bundle in self.fbundles.items():
      bundle.close()

    self.fbundles.clear()

  def write_html(self, html):
    bundle = self.fbundles.get(_FileBundle.FILE_HTML)
    if bundle:
      bundle.write(html)

  def write_text(self, text):
    bundle = self.fbundles.get(_FileBundle.FILE_TEXT)
    if bundle:
      bundle.write(text)


class _Element(object):  # pylint: disable=R0902
  PHRASE_INIT = 0
  PHRASE_STARTED = 1
  PHRASE_REFRESH = 2
  PHRASE_COMPLETE = 3

  def __init__(
      self, bundle, name=None, htmltext=True, action='start',
      parent=None, *args, **kws):

    self.name = name
    self.both = htmltext
    self.bundle = bundle
    self.args = list()
    self.kws = dict()
    self.parent = parent
    self.update_phrase = _Element.PHRASE_INIT
    self.has_args = len(args)
    self.has_child = False
    self.has_refreshed = False
    self.start_tag = None
    self.end_tag = None
    self.nowrap = kws.get('_nowrap', False)
    self.escape = kws.get('_escape', True)
    self.indent = 0
    if self.parent:
      # update parent container
      self.parent.has_child = True
      self.indent = self.parent.indent + 2
      self.nowrap = self.nowrap or self.parent.nowrap

    self.update(action, *args, **kws)

  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc_value, traceback):
    self.update(action='end')

  @staticmethod
  def escape_str(html):
    esc = {
      '"': '&quot;',
      "'": '&apos;',
      '<': '&lt;',
      '>': '&gt;',
    }

    html = html.replace('&', '&amp;')
    for char, val in esc.items():
      html = html.replace(char, val)

    return html

  def _escape(self, html):
    if self.escape:
      html = _Element.escape_str(html)

    return html

  @staticmethod
  def _secure_name(name):
    if name.startswith('_'):
        return None
    else:
        return name.replace('clazz', 'class').replace('_', '-')

  def set_tag(self, start, end):
    self.start_tag = start
    self.end_tag = end

  def set_wrap(self, wrap):
    self.nowrap = not wrap

  def update(self, action, *args, **kws):
    _dict_merge(self.kws, kws)
    self.args.extend(args)

    if len(self.args) > 0:
      self.has_args = True

    if action in ('refresh', 'end'):
      if self.parent:
        self.parent.update(action='refresh')

      elem = ''
      if (action == 'end' or (action == 'refresh' and not self.has_refreshed)) \
          and self.update_phrase == _Element.PHRASE_INIT:
        if self.start_tag or self.name:
          if not self.nowrap or (self.nowrap and not self.parent.nowrap):
            if self.indent != 0:
                elem += '\n'
            elem += '%s<%s' % (' ' * self.indent, self.start_tag or self.name)
          else:
            elem += '<%s' % (self.start_tag or self.name)

          for name in sorted(self.kws.keys()):
            attr = _Element._secure_name(name)
            if attr:
                elem += ' %s="%s"' % (attr, self.kws[name])

          self.kws = dict()
          self.update_phrase = _Element.PHRASE_STARTED

      if action == 'refresh' and not self.has_refreshed:
        self.has_refreshed = True

        # with start tag, don't close
        if self.name and self.update_phrase < _Element.PHRASE_REFRESH:
          elem += '>'

        alem = ''
        for arg in self.args:
          alem += str(arg)

        if self.both:
          self.bundle.write_text(alem)

        elem += self._escape(alem)
        self.args = list()

        self.update_phrase = _Element.PHRASE_REFRESH

      if action == 'end':
        ended = False
        if not self.has_refreshed and self.name:
          if self.has_args or self.has_child:
            elem += '>'
          else:
            elem += '/>'
            ended = True

        alem = ''
        for arg in self.args:
          alem += str(arg)

        if self.both:
          self.bundle.write_text(alem)

        elem += self._escape(alem)
        if not ended and (self.end_tag or self.name):
          if self.end_tag:
            elem += '%s>' % self.end_tag
          elif self.has_args:
            elem += '</%s>' % self.name
          # wrap might be updated before tag ended, treat the intrnal value
          elif self.nowrap:
            elem += '</%s>' % self.name
          else:
            elem += '\n%s</%s>' % (' ' * self.indent, self.name)

      if elem:
        self.bundle.write_html(elem)

  def write(self, *args, **kws):
    self.update(action='deferred', *args, **kws)


class _Table(_Element):
  def __init__(self, bundle, **kws):
    _Element.__init__(self, bundle, 'table', **kws)

  class _Tr(_Element):
    def __init__(self, bundle, **kws):
      _Element.__init__(self, bundle, 'tr', **kws)

    def th(self, *args, **kws):
      with _Th(self.bundle, self, *args, **kws):
        pass

    def wth(self, *args, **kws):
      return _Th(self.bundle, self, *args, **kws)

    def td(self, *args, **kws):
      with _Td(self.bundle, self, *args, **kws):
        pass

    def wtd(self, *args, **kws):
      return _Td(self.bundle, self, *args, **kws)

  def tr(self, **kws):
    return _Table._Tr(self.bundle, parent=self, **kws)


class _Partical(_Element):
  def __init__(self, bundle, name, htmltext=True, action='start',
      parent=None, *args, **kws):
    _Element.__init__(
      self, bundle, name, htmltext, action, parent, *args, **kws)

  class _Comment(_Element):
    def __init__(self, bundle, parent, *args, **kws):
      _Element.__init__(
        self, bundle, '', False, 'start', parent, *args, **kws)
      self.set_tag('!--', '--')

  def comment(self, *args):
    with _Partical._Comment(self.bundle, self, *args):
      pass

class _Mutliple(_Partical):
  def __init__(self, bundle, name, htmltext=True, action='start',
      parent=None, *args, **kws):
    _Partical.__init__(self, bundle, name, htmltext, action, parent, *args, **kws)

  class _A(_Element):
    def __init__(self, bundle, parent=None, *args, **kws):
      _Element.__init__(self, bundle, 'a', True, 'start', parent, *args, **kws)

  def a(self, *args, **kws):
    with _Mutliple._A(self.bundle, self, *args, **kws):
      pass

  def button(self, *args, **kws):
    with _Button(self.bundle, self, *args, **kws):
      pass

  def wbutton(self, *args, **kws):
    return _Button(self.bundle, self, *args, **kws)

  def code(self, *args, **kws):
    with _Code(self.bundle, parent=self, *args, **kws):
      pass

  def wcode(self, *args, **kws):
    return _Code(self.bundle, parent=self, *args, **kws)

  def div(self, **kws):
    return _Div(self.bundle, parent=self, **kws)

  def h2(self, *args, **kws):
    with _H2(self.bundle, self, *args, **kws):
      pass

  def wh2(self, *args, **kws):
    return _H2(self.bundle, self, *args, **kws)

  def h5(self, *args, **kws):
    with _H5(self.bundle, self, *args, **kws):
      pass

  def wh5(self, *args, **kws):
    return _H5(self.bundle, self, *args, **kws)

  def nav(self, *args, **kws):
    return _Nav(self.bundle, parent=self, *args, **kws)

  def p(self, *args, **kws):
    with _P(self.bundle, self, *args, **kws):
      pass

  def wpre(self, *args, **kws):
    return _Pre(self.bundle, self, *args, **kws)

  def pre(self, *args, **kws):
    with _Pre(self.bundle, self, *args, **kws):
      pass

  def span(self, *args, **kws):
    with _Span(self.bundle, self, *args, **kws):
      pass

  def wspan(self, *args, **kws):
    return _Span(self.bundle, self, *args, **kws)

  def table(self, **kws):
    return _Table(self.bundle, parent=self, **kws)


class _Button(_Mutliple):
  def __init__(self, bundle, parent=None, *args, **kws):
    _Mutliple.__init__(
      self, bundle, 'button', True, 'start', parent, *args, **kws)


class _Code(_Mutliple):
  def __init__(self, bundle, *args, **kws):
    _Mutliple.__init__(self, bundle, 'code', *args, **kws)


class _Div(_Mutliple):
  def __init__(self, bundle, *args, **kws):
    _Mutliple.__init__(self, bundle, 'div', *args, **kws)


class _H2(_Mutliple):
  def __init__(self, bundle, parent=None, *args, **kws):
    _Mutliple.__init__(self, bundle, 'h2', True, 'start', parent, *args, **kws)


class _H5(_Mutliple):
  def __init__(self, bundle, parent=None, *args, **kws):
    _Mutliple.__init__(self, bundle, 'h5', True, 'start', parent, *args, **kws)


class _Nav(_Mutliple):
  def __init__(self, bundle, *args, **kws):
    _Mutliple.__init__(self, bundle, 'nav', *args, **kws)


class _P(_Mutliple):
  def __init__(self, bundle, parent=None, *args, **kws):
    _Mutliple.__init__(self, bundle, 'p', True, 'start', parent, *args, **kws)


class _Pre(_Mutliple):
  def __init__(self, bundle, parent=None, *args, **kws):
    _Mutliple.__init__(self, bundle, 'pre', True, 'start', parent, *args, **kws)


class _Span(_Mutliple):
  def __init__(self, bundle, parent=None, *args, **kws):
    _Mutliple.__init__(
      self, bundle, 'span', True, 'start', parent, *args, **kws)


class _Th(_Mutliple):
  def __init__(self, bundle, parent=None, *args, **kws):
    _Mutliple.__init__(self, bundle, 'th', True, 'start', parent, *args, **kws)


class _Td(_Mutliple):
  def __init__(self, bundle, parent=None, *args, **kws):
    _Mutliple.__init__(self, bundle, 'td', True, 'start', parent, *args, **kws)


class _Head(_Partical):
  def __init__(self, bundle, **kws):
    _Partical.__init__(self, bundle, 'head', **kws)

  class _Title(_Element):
    def __init__(self, bundle, parent, *args, **kws):
      _Element.__init__(
        self, bundle, 'title', True, 'start', parent, *args, **kws)

  def title(self, *args):
    with _Head._Title(self.bundle, self, *args):
      pass

  class _Meta(_Element):
    def __init__(self, bundle, **kws):
      _Element.__init__(self, bundle, 'meta', htmltext=False, **kws)

  def meta(self, **kws):
    with _Head._Meta(self.bundle, parent=self, **kws):
      pass

  class _Link(_Element):
    def __init__(self, bundle, **kws):
      _Element.__init__(self, bundle, 'link', **kws)

  def link(self, **kws):
    with _Head._Link(self.bundle, parent=self, **kws):
      pass


class _Body(_Mutliple):
  def __init__(self, bundle, **kws):
    _Mutliple.__init__(self, bundle, 'body', **kws)

  class _Script(_Element):
    def __init__(self, bundle, parent, *args, **kws):
      _Element.__init__(
        self, bundle, 'script', False, 'start', parent,
        *args if len(args) > 0 else '', **kws)

  def script(self, *args, **kws):
    with _Body._Script(self.bundle, self, *args, **kws):
      pass


class FormattedFile(_Element):
  def __init__(self, name, format):  # pylint: disable=W0622
    bundle = dict()

    fname, _ = os.path.splitext(name)
    format = format.lower()
    if format in ('text', 'all'):
      if format == 'all':
        name = '%s.txt' % fname

      bundle[_FileBundle.FILE_TEXT] = name

    if format in ('htm', 'html', 'all'):
      if format == 'all':
        name = '%s.html' % fname

      bundle[_FileBundle.FILE_HTML] = name

    _Element.__init__(self, _FileBundle(bundle), 'html')

  def __exit__(self, exc_type, exc_value, traceback):
    self.close()

  def close(self):
    self.update(action='end')
    self.bundle.close()

  def head(self):
    return _Head(self.bundle, parent=self)

  def body(self):
    return _Body(self.bundle, parent=self)

  @staticmethod
  def open(name, format):  # pylint: disable=W0622
    return FormattedFile(name, format)


TOPIC_ENTRY = 'FormattedFile'
