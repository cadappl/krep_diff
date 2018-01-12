
# pylint: disable=W0622
class _Writer(object):
    def __init__(self, writer, format):
        self.writer = writer
        self.format = format

    @staticmethod
    def css(css, name='class'):
        if css:
            if name:
                return ' %s="%s"' % (name, css)
            else:
                return '%s' % css
        else:
            return ''

    def write(self, *args, **kws):
        format = kws.get('format')
        if format is None or format == self.format:
            for arg in args:
                self.writer.write(arg.encode('utf-8'))


class FormattedItem(object):
    def __init__(
            self, text, link=None, tag=None, format=None, id=None, css=None):
        self.text = text
        self.link = link
        self.id = id
        self.css = css
        self.tag = tag
        self.format = format

    def __str__(self):
        if self.format == FormattedFile.TEXT:
            text = self.text
        else:
            if isinstance(self.text, (list, tuple)):
                text = ''
                for item in self.text:
                    if isinstance(item, FormattedItem):
                        text += str(item)
                    else:
                        text += item
            else:
                text = self.text

            if self.tag:
                text = '<%s>%s</%s>' % (self.tag, text, self.tag)
            elif self.link:
                text = '<a%s%s%s>%s</a>' % (
                    _Writer.css(self.css),
                    _Writer.css(self.id, 'id'),
                    _Writer.css(self.link, 'href'),
                    text)

        return text


class FormatDiv(_Writer):
    def __init__(self, writer, format, css=None):
        _Writer.__init__(self, writer, format)
        self.css = css

    def __enter__(self):
        self.write(
            '<div%s>\n' % FormatDiv.css(self.css),
            format=FormattedFile.HTML)

    def __exit__(self, exc_type, exc_value, traceback):
        self.write('</div>\n', format=FormattedFile.HTML)


class FormatTable(_Writer):
    class FormatRow(_Writer):
        def __init__(self, writer, format, column=None):
            _Writer.__init__(self, writer, format)
            self.column = column

        def row(self, *args, **kws):
            def _text(items):
                if isinstance(items, (list, tuple)):
                    ret = ''
                    for item in items:
                        ret += _text(item)

                    return ret
                else:
                    return str(items)

            self.write(
                '<tr%s>\n' % FormatTable.css(kws.get('tr_css')),
                format=FormattedFile.HTML)

            td_csses = kws.get('td_csses')
            for k, arg in enumerate(args):
                self.write(
                    '<td%s>' % FormatTable.css(td_csses and td_csses[k]) +
                    _text(arg) + '</td>\n', format=FormattedFile.HTML)
                if self.column and len(self.column) > k and self.column[k]:
                    fmt = '%%-%ds' % (self.column[k] + 2)
                    self.write(fmt % _text(arg), format=FormattedFile.TEXT)
                else:
                    self.write(_text(arg), format=FormattedFile.TEXT)

            self.write('</tr>', format=FormattedFile.HTML)
            self.write('\n')

    def __init__(self, writer, format, column=None, css=None):
        _Writer.__init__(self, writer, format)
        self.css = css
        self.column = column

    def __enter__(self):
        self.write(
            '<table%s>\n' % FormatTable.css(self.css),
            format=FormattedFile.HTML)
        return FormatTable.FormatRow(self.writer, self.format, self.column)

    def __exit__(self, exc_type, exc_value, traceback):
        self.write('</table>\n', format=FormattedFile.HTML)


class FileWithFormat(_Writer):
    def __init__(self, name, title, format, css=None):
        self.file = open(name, 'wb')
        _Writer.__init__(self, self.file, format)

        self.write(
            '<html>\n' +
            '  <title>' + title + '</title>\n',
            format=FormattedFile.HTML)
        self.write(
            '%s<body>\n' % FileWithFormat.css(css, name=''),
            format=FormattedFile.HTML)

        self.write(title + '\n', format=FormattedFile.TEXT)
        self.write('=' * (len(title) + 1) + '\n', format=FormattedFile.TEXT)

    def close(self):
        self.write('</body>\n</html>', format=FormattedFile.HTML)
        self.file.close()

    def section(self, title):
        self.write('<h5>' + title + '</h5>\n', format=FormattedFile.HTML)

        self.write('\n' + title + '\n', format=FormattedFile.TEXT)
        self.write('-' * (len(title) + 1) + '\n', format=FormattedFile.TEXT)

    def div(self, css=None):
        return FormatDiv(self.file, self.format, css)

    def table(self, column=None, css=None):
        return FormatTable(self.file, self.format, column, css=css)

    def item(self, text, link=None, tag=None, id=None, css=None):
        return FormattedItem(
            text, link=link, tag=tag, format=self.format, id=id, css=css)


class FormattedFile(object):
    TEXT = 'text'
    HTML = 'html'
    ALL = 'all'

    def __init__(self, name, title, format, css=None):
        self.name = name
        self.file = None
        self.title = title
        self.format = format
        self.css = css

    def __enter__(self):
        self.file = FormattedFile.open(
            self.name, self.title, self.format, css=self.css)
        return self.file

    def __exit__(self, exc_type, exc_value, traceback):
        if self.file:
            self.file.close()

    @staticmethod
    def open(name, title, format, css=None):
        return FileWithFormat(name, title, format, css)
# pylint: enable=W0622


TOPIC_ENTRY = 'FormattedFile,FormattedItem'
