# 网页版（GitHub Pages）

这个目录会被 GitHub Pages 发布成网站：

**https://jiangnanqing188.github.io/miband8pro-timetable-watchface/**

`index.html` 是 `wf/jspack/app-template.html` 打包出来的单文件应用
（由 `node wf/jspack/bundle.mjs` 生成，产物同时写到 `out/kebiao-app.html`）。

改完源码后重新生成并更新这里：

```bash
node wf/jspack/bundle.mjs
cp out/kebiao-app.html docs/index.html
```

打开就是手机 App：填开学日期 → 填课表 → 点「生成表盘文件」→ 下载 `.face`。
所有数据留在浏览器本地，不上传任何服务器。
