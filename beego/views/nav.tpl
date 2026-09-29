<nav>
  <a href="{{urlfor "FortunesController.Index"}}">Fortunes</a>
  {{range .NavIds}}
  <a href="{{urlfor "FortunesController.Show" ":id" .}}" {{if eq . $.CurrentId}}class="active"{{end}}>#{{.}}</a>
  {{end}}
</nav>
