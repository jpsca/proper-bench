// The Beego reference app for the Proper benchmarks: the same three routes as
// benchmarks/app, over the same SQLite file.
//
//	go build -o beego-bench . && PORT=8123 ./beego-bench
package main

import (
	"fmt"
	"html/template"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strconv"

	"github.com/beego/beego/v2/client/orm"
	"github.com/beego/beego/v2/server/web"
	"github.com/beego/beego/v2/server/web/context"
	_ "github.com/mattn/go-sqlite3"
)

type Fortune struct {
	Id      int    `orm:"pk;column(id)"`
	Message string `orm:"column(message)"`
}

func (f *Fortune) TableName() string { return "fortune" }

type BenchController struct {
	web.Controller
}

func (c *BenchController) Plaintext() {
	c.Ctx.Output.Header("Content-Type", "text/plain; charset=utf-8")
	c.Ctx.WriteString("Hello, World!")
}

func (c *BenchController) Json() {
	c.Data["json"] = map[string]string{"message": "Hello, World!"}
	c.ServeJSON()
}

func (c *BenchController) Fortunes() {
	var rows []Fortune
	if _, err := orm.NewOrm().QueryTable("fortune").All(&rows); err != nil {
		c.Abort("500")
		return
	}
	rows = append(rows, Fortune{Id: 0, Message: "Additional fortune added at request time."})
	sort.Slice(rows, func(i, j int) bool { return rows[i].Message < rows[j].Message })
	c.Data["fortunes"] = rows
	c.TplName = "fortunes.tpl"
}

// --- The page route: what a CRUD app's "show" does ---

// PadController stands in for the other resources of the app.
type PadController struct {
	web.Controller
}

func (c *PadController) Show() {
	c.Ctx.WriteString("pad")
}

type FortunesController struct {
	web.Controller
}

func (c *FortunesController) Index() {
	var rows []Fortune
	if _, err := orm.NewOrm().QueryTable("fortune").All(&rows); err != nil {
		c.Abort("500")
		return
	}
	c.Data["fortunes"] = rows
	c.Data["NavIds"] = []int{1, 2, 3}
	c.Data["CurrentId"] = 0
	c.Layout = "layout.tpl"
	c.LayoutSections = map[string]string{"Nav": "nav.tpl"}
	c.TplName = "fortunes/index.tpl"
}

func (c *FortunesController) Show() {
	id, err := strconv.Atoi(c.Ctx.Input.Param(":id"))
	if err != nil {
		c.Abort("404")
		return
	}
	fortune := Fortune{Id: id}
	if err := orm.NewOrm().Read(&fortune); err != nil {
		c.Abort("404")
		return
	}
	c.Data["fortune"] = fortune
	c.Data["NavIds"] = []int{1, 2, 3}
	c.Data["CurrentId"] = id
	c.Layout = "layout.tpl"
	c.LayoutSections = map[string]string{"Nav": "nav.tpl"}
	c.TplName = "fortunes/show.tpl"
}

var securityHeaders = map[string]string{
	"X-Frame-Options":                   "SAMEORIGIN",
	"X-XSS-Protection":                  "1; mode=block",
	"X-Download-Options":                "noopen",
	"X-Permitted-Cross-Domain-Policies": "none",
	"Referrer-Policy":                   "strict-origin-when-cross-origin",
}

// checkRequestOrigin rejects cross-site state-changing requests; reads go through.
func checkRequestOrigin(ctx *context.Context) {
	switch ctx.Input.Method() {
	case "GET", "HEAD", "OPTIONS":
		return
	}
	origin := ctx.Input.Header("Origin")
	secFetchSite := ctx.Input.Header("Sec-Fetch-Site")
	if (origin == "" && secFetchSite == "") || secFetchSite == "same-origin" || secFetchSite == "none" {
		return
	}
	if u, err := url.Parse(origin); err == nil && u.Host == ctx.Input.Host() {
		return
	}
	ctx.Abort(403, "403")
}

func setSecurityHeaders(ctx *context.Context) {
	for name, value := range securityHeaders {
		if ctx.ResponseWriter.Header().Get(name) == "" {
			ctx.Output.Header(name, value)
		}
	}
}

func main() {
	here, _ := filepath.Abs(filepath.Dir(os.Args[0]))
	dbPath := os.Getenv("FORTUNES_DB")
	if dbPath == "" {
		dbPath = filepath.Join(here, "..", "app", "fortunes.db")
	}
	orm.RegisterDriver("sqlite3", orm.DRSqlite)
	if err := orm.RegisterDataBase("default", "sqlite3", dbPath); err != nil {
		panic(err)
	}
	orm.RegisterModel(new(Fortune))

	port := 8123
	if p := os.Getenv("PORT"); p != "" {
		fmt.Sscanf(p, "%d", &port)
	}
	web.BConfig.RunMode = web.PROD
	web.BConfig.Listen.HTTPPort = port
	web.BConfig.Listen.HTTPAddr = "127.0.0.1"
	web.BConfig.Log.AccessLogs = false
	web.BConfig.WebConfig.AutoRender = true
	web.BConfig.WebConfig.ViewsPath = filepath.Join(here, "views")
	web.BConfig.WebConfig.EnableXSRF = false
	_ = template.HTMLEscapeString // html/template escapes the messages

	web.Router("/plaintext", &BenchController{}, "get:Plaintext")
	web.Router("/json", &BenchController{}, "get:Json")
	web.Router("/fortunes", &BenchController{}, "get:Fortunes")

	// Fifty other resources, registered before the page, as in an app of that size.
	for n := 0; n < 50; n++ {
		web.Router(fmt.Sprintf("/pad%d/:id:int", n), &PadController{}, "get:Show")
	}
	// The filters run for the page routes only, like the concerns of Proper's
	// page controller. Headers go in before the controller runs, since the
	// auto-render writes the body before the AfterExec filters.
	web.InsertFilter("/fortunes/*", web.BeforeRouter, checkRequestOrigin)
	web.InsertFilter("/fortunes/*", web.BeforeExec, setSecurityHeaders)
	web.Router("/fortunes/all", &FortunesController{}, "get:Index")
	web.Router("/fortunes/:id:int", &FortunesController{}, "get:Show")
	web.Run()
}
