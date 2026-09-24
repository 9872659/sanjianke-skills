# 目录、大纲、批量与 Serverless

## 目录（toc 对象）

目录是按输入文档里的 `<h?>` 标签生成的：先把大纲生成一份 XML，再用 XSLT 转成 HTML 排版进 PDF。

```bash
# 只在正文前插一个目录
wkhtmltopdf toc body.html out.pdf

# 封面 + 目录 + 正文（对象按顺序排）
wkhtmltopdf cover cover.html toc --xsl-style-sheet my-toc.xsl body.html out.pdf

# 自定义目录样式：先导出默认 XSL 作为起点
wkhtmltopdf --dump-default-toc-xsl > my-toc.xsl
```

注意：`--toc-*`、`--disable-dotted-lines` 这一类选项**只对默认样式表生效**；
一旦用了 `--xsl-style-sheet`，目录长什么样完全由你的 XSL 决定。

## 大纲（PDF 书签）

```bash
# 导出大纲 XML，先看清目录结构对不对
wkhtmltopdf --dump-outline toc.xml body.html out.pdf

# 控制书签深度；不需要书签就关掉
wkhtmltopdf --outline-depth 2 body.html out.pdf
wkhtmltopdf --no-outline body.html out.pdf

# 某个页面对象不参与目录与书签
wkhtmltopdf --exclude-from-outline appendix.html out.pdf
```

大纲 XML 的命名空间是 `http://wkhtmltopdf.org/outline`，根节点 `outline`，
下面是一层层 `item`，每个 `item` 有这些属性：

| 属性 | 含义 |
|---|---|
| `title` | 章节标题 |
| `page` | 章节所在页码 |
| `link` | 指向该章节的链接 |
| `backLink` | 章节回跳目录用的锚点 |

调试目录排版时，先 `--dump-outline` 看结构，再决定是改 HTML 里的标题层级，还是改 XSL。

## 页眉页脚 HTML 里的变量回填

命令行给 `--header-html` 传页面时，页码等变量是通过**查询串**带过去的，
所以页眉 HTML 要自己解析并写进 DOM。官方给的范式（简化版）：

```html
<!DOCTYPE html>
<html>
<head>
<script>
function subst() {
  var vars = {};
  var qs = document.location.search.substring(1).split('&');
  for (var i in qs) {
    if (qs.hasOwnProperty(i)) {
      var kv = qs[i].split('=', 2);
      vars[kv[0]] = decodeURI(kv[1]);
    }
  }
  var names = ['page', 'frompage', 'topage', 'webpage', 'section', 'subsection',
               'date', 'isodate', 'time', 'title', 'doctitle', 'sitepage', 'sitepages'];
  for (var j in names) {
    if (!names.hasOwnProperty(j)) continue;
    var els = document.getElementsByClassName(names[j]);
    for (var k = 0; k < els.length; ++k) {
      els[k].textContent = vars[names[j]];
    }
  }
}
</script>
</head>
<body style="border:0; margin:0;" onload="subst()">
  <table style="width:100%; border-bottom:1px solid #000;">
    <tr>
      <td class="section"></td>
      <td style="text-align:right">
        Page <span class="page"></span> of <span class="topage"></span>
      </td>
    </tr>
  </table>
</body>
</html>
```

要点：类名要和变量名一致、`onload` 里调用 `subst()`、请求参数用 URL 编码。

也可以用 `--replace <name> <value>` 在纯文字页眉页脚里做自定义替换。

## 批量转换

逐条命令启动进程时，初始化的开销会被放大。用 `--read-args-from-stdin`：
命令行参数作为公共参数，stdin 每行是一个独立任务的参数。

```bash
# cmds 内容示例：
#   input1.html out1.pdf
#   input2.html out2.pdf
wkhtmltopdf --read-args-from-stdin --enable-local-file-access --quiet < cmds
```

每行也支持完整对象写法，比如一行里带封面与目录：

```
cover cover.html toc body.html out.pdf
```

配套建议：

- 用 `--quiet`（等同 `--log-level none`）减少日志噪音，但要自己检查输出文件是否存在
- 批量时先把公共选项（纸张、边距、页眉页脚、`--enable-local-file-access`）放在公共参数里
- 单个任务失败不该拖垮整批：脚本里要逐行判断输出文件是否生成

## Serverless / 容器

**AWS Lambda**：官方提供 Amazon Linux 2 的 lambda zip，形态是 layer。解包后：
- 二进制在 `bin/`，库在 `lib/`，字体配置在 `fonts/`
- 运行前需要 `LD_LIBRARY_PATH=/opt/lib` 与 `FONTCONFIG_PATH=/opt/fonts`
- 本地验证可用官方给的容器命令思路：起一个 Amazon Linux 容器，把 layer 挂到 `/opt`，
  再带着上面两个环境变量调用 `/opt/bin/wkhtmltopdf`
- 无字体配置（`FONTCONFIG_PATH`）时中文等非拉丁字体会渲染失败或变方块

**容器镜像**：
- 通用构建依赖 glibc，**Alpine（musl）跑不起来**，换 Debian/Ubuntu 系基础镜像
- 镜像里要装中文字体（否则中文缺字）
- 只在自己控制的 HTML 上跑；处理用户内容时加 AppArmor/SELinux 之类的强制访问控制

## 安全底线

官方在项目状态页给出的建议很直接：

- **不要用不可信 HTML**：其中的 JS 可以完全接管运行它的服务器
- 用 AppArmor 或 SELinux 之类的强制访问控制限制这个进程（官方另有一份推荐的
  AppArmor 策略可参考）
- 如果只是生成自己控制的报表 HTML，官方也建议对比一下别的 HTML→PDF 方案
  （例如 WeasyPrint 这类，或商业工具）
- 目标站点依赖大量动态 JS 时，官方建议改用无头浏览器方案（例如 puppeteer 系）

换句话说：这个工具适合「HTML 在我手里」的场景，不适合当面向用户的内容转换服务，
除非你把它关进沙箱里。
