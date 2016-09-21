
# pylint: disable=W0622
class _Writer(object):
    def __init__(self, writer, format):
        self.writer = writer
        self.format = format

    def write(self, *args, **kws):
        format = kws.get('format')
        if format is None or format == self.format:
            for arg in args:
                self.writer.write(arg)


class FormattedItem(object):
    def __init__(self, text, link=None, tag=None, format=None):
        self.text = text
        self.link = link
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

            if self.link:
                text = '<a href="%s">%s</a>' % (self.link, text)
            if self.tag:
                text = '<%s>%s</%s>' % (self.tag, text, self.tag)

        return text

class FormatTable(_Writer):
    class FormatRow(_Writer):
        def __init__(self, writer, format, column=None):
            _Writer.__init__(self, writer, format)
            self.column = column

        def row(self, *args):
            def _text(items):
                if isinstance(items, (list, tuple)):
                    ret = ''
                    for item in items:
                        ret += _text(item)

                    return ret
                else:
                    return str(items)

            self.write('<tr>\n', format=FormattedFile.HTML)

            for k, arg in enumerate(args):
                self.write(
                    '<td>' + _text(arg) + '</td>\n', format=FormattedFile.HTML)
                if self.column and len(self.column) > k and self.column[k]:
                    fmt = '%%-%ds' % (self.column[k] + 2)
                    self.write(fmt % _text(arg), format=FormattedFile.TEXT)
                else:
                    self.write(_text(arg), format=FormattedFile.TEXT)

            self.write('</tr>', format=FormattedFile.HTML)
            self.write('\n')

    def __init__(self, writer, format, column=None):
        _Writer.__init__(self, writer, format)
        self.column = column

    def __enter__(self):
        self.write('<table class="hoverTable">\n', format=FormattedFile.HTML)
        return FormatTable.FormatRow(self.writer, self.format, self.column)

    def __exit__(self, exc_type, exc_value, traceback):
        self.write('</table>\n', format=FormattedFile.HTML)


class FileWithFormat(_Writer):
    def __init__(self, name, title, format):
        self.file = open(name, 'wb')
        _Writer.__init__(self, self.file, format)

        self.write(
            '<html>\n' +
            '  <title>' + title + '</title>\n',
            format=FormattedFile.HTML)
        self.write(
            '<style type="text/css">\n'
            '  pre,code{font-family:courier;}\n'
            '  h5 {font-family: Georgia, serif;}\n'
            '  .hoverTable{font-family: verdana,arial,sans-serif;'
            'width:100%;border-collapse:collapse;font-size:11px;'
            'text-align:left;}\n'
            '  .hoverTable td{padding:3px;}\n'
            '  .hoverTable tr{background: #b8d1f3;}\n'
            '  .hoverTable tr:nth-child(odd){background: #dae5f4;}\n'
            '  .hoverTable tr:nth-child(even){background: #ffffff;}\n'
            '  .hoverTable tr:hover {background-color: #bbbbbb;}\n'
            '</style>\n'
            '<body>\n',
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

    def table(self, column=None):
        return FormatTable(self.file, self.format, column)

    def item(self, text, link=None, tag=None):
        return FormattedItem(text, link=link, tag=tag, format=self.format)


class FormattedFile(object):
    TEXT = 'text'
    HTML = 'html'
    ALL = 'all'

    def __init__(self, name, title, format):
        self.name = name
        self.file = None
        self.title = title
        self.format = format

    def __enter__(self):
        self.file = FormattedFile.open(self.name, self.title, self.format)
        return self.file

    def __exit__(self, exc_type, exc_value, traceback):
        if self.file:
            self.file.close()

    @staticmethod
    def open(name, title, format):
        return FileWithFormat(name, title, format)
# pylint: enable=W0622


TOPIC_ENTRY = 'FormattedFile,FormattedItem'
