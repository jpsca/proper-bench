<article id="fortune-{{.fortune.Id}}">
  <h1>Fortune #{{.fortune.Id}}</h1>
  <blockquote>{{.fortune.Message}}</blockquote>
  <p><a href="{{urlfor "FortunesController.Index"}}">Back</a></p>
</article>
