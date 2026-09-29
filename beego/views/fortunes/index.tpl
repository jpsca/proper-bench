<ul>
{{range .fortunes}}
  <li><a href="{{urlfor "FortunesController.Show" ":id" .Id}}">{{.Message}}</a></li>
{{end}}
</ul>
