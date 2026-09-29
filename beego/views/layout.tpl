<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{{if .Title}}{{.Title}}{{else}}Fortunes{{end}}</title>
</head>
<body>
  {{.Nav}}
  <main class="container">
    {{.LayoutContent}}
  </main>
</body>
</html>
