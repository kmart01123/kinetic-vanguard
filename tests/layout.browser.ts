import assert from "node:assert/strict";
import test from "node:test";
import { pathToFileURL } from "node:url";
import { chromium, firefox, type Page } from "playwright";
import { executeBuild } from "../src/build.js";
import { loadAuthority } from "../src/load.js";

const defaultReferenceFragment="#category=common_features&topic=common_features_how_to_play_topic";
const desktopViewports = [
  { width: 1640, height: 860 },
  { width: 1440, height: 900 },
  { width: 1366, height: 768 },
  { width: 1280, height: 800 },
  { width: 1024, height: 768 }
];
const browserLaunchOptions = { headless: true, timeout: 30_000 } as const;
const availableDesktopBrowsers = [
  { id: "chromium", name: "Chromium", type: chromium },
  { id: "firefox", name: "Firefox", type: firefox }
] as const;
const requestedBrowserIds = new Set((process.env.KV_LAYOUT_BROWSERS ?? "chromium").split(","));
const unsupportedBrowserIds = [...requestedBrowserIds].filter(
  id => !availableDesktopBrowsers.some(browser => browser.id === id)
);
if (unsupportedBrowserIds.length > 0) {
  throw new Error(`Unsupported layout browser selection: ${unsupportedBrowserIds.join(", ")}`);
}
const desktopBrowsers = availableDesktopBrowsers.filter(browser => requestedBrowserIds.has(browser.id));
if (desktopBrowsers.length === 0) {
  throw new Error("At least one layout browser must be selected");
}
const nativeSelectIndicatorAllowance = 24;

const readSubclassProgressionLayout=(page:Page)=>page.evaluate(()=>{
  const table=[...document.querySelectorAll<HTMLTableElement>("#entity-subclass_feature_reference table")].find(candidate=>[...candidate.querySelectorAll("thead th")].map(cell=>cell.textContent).join("|")==="Level|Feature");if(!table)throw new Error("Missing Subclass Feature Reference progression table");
  const wrapper=table.closest<HTMLElement>(".table-scroll")!,headers=[...table.querySelectorAll<HTMLTableCellElement>("thead th")],levelCells=[...table.querySelectorAll<HTMLTableCellElement>("tr > :first-child")];let levelTextFits=true,levelTextSingleLine=true,levelContentUnclipped=true;
  for(const cell of levelCells){const style=getComputedStyle(cell),probe=document.createElement("span");probe.textContent=cell.textContent??"";probe.style.cssText="position:fixed;visibility:hidden;white-space:nowrap;inset:0 auto auto 0";probe.style.font=style.font;probe.style.letterSpacing=style.letterSpacing;document.body.append(probe);const naturalWidth=probe.getBoundingClientRect().width;probe.remove();const contentWidth=cell.clientWidth-Number.parseFloat(style.paddingLeft)-Number.parseFloat(style.paddingRight);if(contentWidth+1<naturalWidth)levelTextFits=false;const range=document.createRange();range.selectNodeContents(cell);const lineTops=new Set([...range.getClientRects()].filter(rect=>rect.width>0&&rect.height>0).map(rect=>Math.round(rect.top*100)/100));if(lineTops.size!==1)levelTextSingleLine=false;if(cell.scrollWidth>cell.clientWidth+1||style.textOverflow==="ellipsis")levelContentUnclipped=false;}
  const tableRect=table.getBoundingClientRect(),wrapperRect=wrapper.getBoundingClientRect();
  return{headers:headers.map(cell=>cell.textContent),tableWidth:tableRect.width,wrapperWidth:wrapper.clientWidth,scrollable:wrapper.scrollWidth>wrapper.clientWidth+1,tableContained:tableRect.left>=wrapperRect.left-1&&tableRect.right<=wrapperRect.right+1,levelColumnWidth:headers[0]!.getBoundingClientRect().width,featureColumnWidth:headers[1]!.getBoundingClientRect().width,levelTextFits,levelTextSingleLine,levelContentUnclipped,documentOverflow:document.documentElement.scrollWidth-document.documentElement.clientWidth};
});

test("master Name select renders canonical progression and stable renamed routes in configured browsers",async()=>{
  const result=await executeBuild("prototype");const {authority}=await loadAuthority();const url=pathToFileURL(result.htmlPath).href+defaultReferenceFragment;
  const rulesAreas=authority.vocabularies.rules_areas!;const expectedGroups=[...rulesAreas].sort((a,b)=>a.order-b.order).map(area=>area.label);
  const featureIds=new Set(authority.entities.filter(entity=>entity.kind==="feature").map(entity=>entity.id));
  const expectedFeatures=Object.fromEntries(rulesAreas.map(area=>[area.label,authority.entities.filter(entity=>entity.kind==="feature"&&entity.presentation_metadata.primary_rules_area===area.id).sort((a,b)=>Number(a.level)-Number(b.level)||(a.title<b.title?-1:a.title>b.title?1:0)||(a.id<b.id?-1:a.id>b.id?1:0)).map(entity=>entity.id)]));
  for(const engine of desktopBrowsers){
    const browser=await engine.type.launch(browserLaunchOptions);
    try{
      const page=await browser.newPage({viewport:{width:1366,height:768}});await page.goto(url);await page.evaluate(()=>{const push=history.pushState.bind(history);(window as any).__namePushCount=0;history.pushState=(...args)=>{(window as any).__namePushCount++;return push(...args);};});
      const readGroups=()=>page.locator("#name-select optgroup").evaluateAll(groups=>groups.map(group=>({label:(group as HTMLOptGroupElement).label,ids:[...group.querySelectorAll<HTMLOptionElement>(":scope > option")].map(option=>option.value),labels:[...group.querySelectorAll<HTMLOptionElement>(":scope > option")].map(option=>option.textContent??"")})));
      const observed=await readGroups();assert.deepEqual(observed.map(group=>group.label),expectedGroups,engine.name+" group order");
      for(const group of observed)assert.deepEqual(group.ids.filter(id=>featureIds.has(id)),expectedFeatures[group.label],engine.name+" "+group.label+" feature order");
      const pyrokinesis=observed.find(group=>group.label==="Pyrokinesis")!;assert.ok(pyrokinesis.ids.indexOf("thermal_fracture")<pyrokinesis.ids.indexOf("furnace_strike"),engine.name+" Thermal Fracture before Furnace Strike");
      const advanced=observed.find(group=>group.label==="Advanced Training")!;assert.deepEqual(advanced.labels.slice(0,2),["Deflection Screen","Phase Step"],engine.name+" cleaned Advanced Training labels");
      const pyroFilter=page.locator('input[data-facet="rules_area"][value="pyrokinesis"]');await pyroFilter.check();
      const filtered=await readGroups();assert.deepEqual(filtered.map(group=>group.label),["Pyrokinesis"],engine.name+" filtered groups");assert.deepEqual(filtered[0]!.ids,pyrokinesis.ids,engine.name+" filtered rebuild order");await pyroFilter.uncheck();
      const advancedFilter=page.locator('input[data-facet="rules_area"][value="advanced_training"]');await advancedFilter.check();
      const rebuiltAdvanced=await readGroups();assert.deepEqual(rebuiltAdvanced.map(group=>group.label),["Advanced Training"],engine.name+" rebuilt Advanced Training group");assert.deepEqual(rebuiltAdvanced[0]!.labels.slice(0,2),["Deflection Screen","Phase Step"],engine.name+" rebuilt clean labels");
      assert.equal(new Set(rebuiltAdvanced[0]!.ids).size,rebuiltAdvanced[0]!.ids.length,engine.name+" no duplicate Advanced Training options");assert.ok(rebuiltAdvanced[0]!.labels.every(label=>!label.startsWith("Advanced Training I:")&&!label.startsWith("Advanced Training II:")),engine.name+" no rebuilt prefixed labels");
      const resultLabels=await page.locator("#filter-results button").allTextContents();assert.ok(resultLabels.includes("Deflection Screen — Advanced Training"));assert.ok(resultLabels.includes("Phase Step — Advanced Training"));assert.ok(resultLabels.every(label=>!label.startsWith("Advanced Training I:")&&!label.startsWith("Advanced Training II:")));await advancedFilter.uncheck();
      for(const [id,title] of [["advanced_deflection_screen","Deflection Screen"],["advanced_phase_step","Phase Step"]] as const){
        await page.goto(url);await page.evaluate(()=>{const push=history.pushState.bind(history);(window as any).__namePushCount=0;history.pushState=(...args)=>{(window as any).__namePushCount++;return push(...args);};});const historyBefore=0;await page.selectOption("#name-select",id);
        const route=new URL(page.url()).hash;assert.equal(route.startsWith(`#calculator&card=${id}&`),true);assert.equal(await page.locator("#calculator-feature-results > h3").textContent(),title);
        assert.equal(await page.locator("#name-open").count(),0);assert.ok(await page.evaluate(()=>(window as any).__namePushCount)>=historyBefore+1);
        await page.goBack();await page.goForward();assert.equal(await page.locator("#calculator-feature-results > h3").textContent(),title,engine.name+" Forward navigation");
      }
      await page.close();
    }finally{await browser.close();}
  }
});

test("mobile Name and result navigation focus and reveal the selected Calculator card",async()=>{
  const result=await executeBuild("prototype");const url=pathToFileURL(result.htmlPath).href+defaultReferenceFragment;
  for(const engine of desktopBrowsers){
    const browser=await engine.type.launch(browserLaunchOptions);
    try{
      const page=await browser.newPage({viewport:{width:412,height:915}});await page.goto(url);
      const assertFocusedAndVisible=async(title:string)=>{
        await page.waitForFunction(expected=>{const heading=document.querySelector<HTMLElement>("#calculator-feature-results > h3");if(!heading||heading.textContent!==expected)return false;const rect=heading.getBoundingClientRect();return document.activeElement===heading&&rect.top>=-1&&rect.bottom<=innerHeight+1;},title);
      };
      await page.selectOption("#name-select","ball_lightning");await assertFocusedAndVisible("Ball Lightning");assert.match(new URL(page.url()).hash,/^#calculator&card=ball_lightning&/u);
      await page.goto(url);await page.locator('input[data-facet="rules_area"][value="electrokinesis"]').check();await page.getByRole("button",{name:"Ball Lightning — Electrokinesis"}).click();await assertFocusedAndVisible("Ball Lightning");assert.match(new URL(page.url()).hash,/^#calculator&card=ball_lightning&/u);
    }finally{await browser.close();}
  }
});

test("prototype columns and long selected topics fit in desktop browsers", async () => {
  const result = await executeBuild("prototype");
  const url = `${pathToFileURL(result.htmlPath).href}#category=common_features&topic=common_features_advanced_training_progression_topic`;

  for (const engine of desktopBrowsers) {
    const browser = await engine.type.launch(browserLaunchOptions);
    const page = await browser.newPage();
    try {
      for (const viewport of desktopViewports) {
        await page.setViewportSize(viewport);
        await page.goto(url);
        await page.waitForSelector("#rules-content article");

        const layout = await page.evaluate(indicatorAllowance => {
          const sidebar = document.querySelector<HTMLElement>(".controls")!;
          const content = document.querySelector<HTMLElement>(".rules")!;
          const article = content.querySelector<HTMLElement>("article")!;
          const topic = document.querySelector<HTMLSelectElement>("#topic-select")!;
          const sidebarRect = sidebar.getBoundingClientRect();
          const contentRect = content.getBoundingClientRect();
          const articleRect = article.getBoundingClientRect();
          const topicStyle = getComputedStyle(topic);
          const canvas = document.createElement("canvas");
          const context = canvas.getContext("2d")!;
          context.font = topicStyle.font;
          const selectedTopic = topic.selectedOptions.item(0)!.text;
          const selectedTopicWidth = context.measureText(selectedTopic).width;
          const topicHorizontalPadding = parseFloat(topicStyle.paddingLeft) + parseFloat(topicStyle.paddingRight);
          const sidebarRight = Math.max(
            sidebarRect.right,
            ...[...sidebar.querySelectorAll<HTMLElement>("*")].map(element => element.getBoundingClientRect().right)
          );
          const textContained = [...article.querySelectorAll<HTMLElement>("h2, h3, p, aside, li")]
            .every(element => element.scrollWidth <= element.clientWidth);

          return {
            sidebarRight,
            contentLeft: contentRect.left,
            contentRight: contentRect.right,
            articleRight: articleRect.right,
            gap: contentRect.left - sidebarRight,
            documentOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
            textContained,
            selectedTopic,
            selectedTopicFits: selectedTopicWidth + topicHorizontalPadding + indicatorAllowance <= topic.clientWidth
          };
        }, nativeSelectIndicatorAllowance);

        const size = `${engine.name} ${viewport.width}x${viewport.height}`;
        assert.ok(layout.sidebarRight <= layout.contentLeft, `${size}: sidebar.right must not exceed content.left`);
        assert.ok(layout.gap >= 0, `${size}: sidebar and content must have a non-negative visible gap`);
        assert.ok(layout.articleRight <= layout.contentRight, `${size}: article must remain inside the content panel`);
        assert.equal(layout.documentOverflow, 0, `${size}: page must not scroll horizontally`);
        assert.equal(layout.textContained, true, `${size}: headings and body text must remain contained`);
        assert.equal(layout.selectedTopic, "Advanced Training Progression");
        assert.equal(layout.selectedTopicFits, true, `${size}: selected Topic text must fit beside the native indicator`);
      }
    } finally {
      await browser.close();
    }
  }
});

test("prototype deliberately stacks below the two-column breakpoint", async () => {
  const result = await executeBuild("prototype");
  const browser = await chromium.launch(browserLaunchOptions);
  const page = await browser.newPage({ viewport: { width: 760, height: 900 } });

  try {
    await page.goto(pathToFileURL(result.htmlPath).href+defaultReferenceFragment);
    await page.waitForSelector("#rules-content article");
    const layout = await page.evaluate(() => {
      const sidebar = document.querySelector<HTMLElement>(".controls")!.getBoundingClientRect();
      const content = document.querySelector<HTMLElement>(".rules")!.getBoundingClientRect();
      return {
        sidebarBottom: sidebar.bottom,
        contentTop: content.top,
        documentOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth
      };
    });

    assert.ok(layout.contentTop >= layout.sidebarBottom, "stacked content must begin below the sidebar");
    assert.equal(layout.documentOverflow, 0, "stacked page must not scroll horizontally");
  } finally {
    await browser.close();
  }
});

test("Subclass Feature Reference keeps both tables readable across screen and print layouts",async()=>{
  const result=await executeBuild("prototype");const url=pathToFileURL(result.htmlPath).href+"#category=common_features&topic=common_features_subclass_feature_reference_topic";
  const assertProgressionLayout=(layout:Awaited<ReturnType<typeof readSubclassProgressionLayout>>,context:string)=>{assert.deepEqual(layout.headers,["Level","Feature"],context+" progression headers");assert.ok(layout.tableWidth<=layout.wrapperWidth+1,context+" progression table fits its wrapper");assert.equal(layout.scrollable,false,context+" progression table does not scroll horizontally");assert.equal(layout.tableContained,true,context+" progression table remains contained");assert.ok(layout.featureColumnWidth>layout.levelColumnWidth,context+" Feature remains the wider column");assert.equal(layout.levelTextFits,true,context+" Level text fits naturally");assert.equal(layout.levelTextSingleLine,true,context+" Level text remains on one line");assert.equal(layout.levelContentUnclipped,true,context+" Level text is not clipped");assert.equal(layout.documentOverflow,0,context+" progression document overflow");};
  for(const engine of desktopBrowsers){
    const browser=await engine.type.launch(browserLaunchOptions);
    try{
      const page=await browser.newPage({viewport:{width:412,height:915}});await page.goto(url);
      for(const width of [412,320,761]){
        await page.setViewportSize({width,height:915});
        const layout=await page.evaluate(async()=>{
          const table=document.querySelector<HTMLTableElement>("#psi-cost-reference-table")!,wrapper=table.closest<HTMLElement>(".table-scroll")!,firstRow=table.tBodies[0]!.rows[0]!,style=getComputedStyle(wrapper);
          wrapper.scrollLeft=Number.MAX_SAFE_INTEGER;await new Promise<void>(resolve=>requestAnimationFrame(()=>resolve()));
          const wrapperRect=wrapper.getBoundingClientRect(),scrollportLeft=wrapperRect.left+wrapper.clientLeft,scrollportRight=scrollportLeft+wrapper.clientWidth,durationCells=[table.tHead!.rows[0]!.cells[5]!,...[...table.tBodies[0]!.rows].map(row=>row.cells[5]!)];
          const lastColumnReachable=durationCells.every(cell=>{const rect=cell.getBoundingClientRect();return rect.left>=scrollportLeft-1&&rect.right<=scrollportRight+1;});
          const durationContentFits=durationCells.every(cell=>cell.scrollWidth<=cell.clientWidth+1&&cell.scrollHeight<=cell.clientHeight+1&&getComputedStyle(cell).textOverflow!=="ellipsis");
          return{headers:[...table.querySelectorAll("th")].map(cell=>cell.textContent),tableClass:table.className,wrapperTabIndex:wrapper.getAttribute("tabindex"),overflowX:style.overflowX,scrollable:table.scrollWidth>wrapper.clientWidth,scrolled:wrapper.scrollLeft>0,lastColumnReachable,durationContentFits,documentOverflow:document.documentElement.scrollWidth-document.documentElement.clientWidth,levelWhiteSpace:getComputedStyle(firstRow.cells[0]!).whiteSpace,psiWhiteSpace:getComputedStyle(firstRow.cells[3]!).whiteSpace};
        });
        assert.deepEqual(layout.headers,["Level","Feature","Discipline","Psi","Activation","Ongoing Duration"],engine.name+" "+width+"px headers");assert.equal(layout.tableClass,"quick-reference-table");assert.equal(layout.wrapperTabIndex,"0");assert.ok(["auto","scroll"].includes(layout.overflowX));assert.equal(layout.scrollable,true,engine.name+" "+width+"px horizontal table scroll");assert.equal(layout.scrolled,true,engine.name+" "+width+"px reaches the right edge");assert.equal(layout.lastColumnReachable,true,engine.name+" "+width+"px duration column is fully reachable");assert.equal(layout.durationContentFits,true,engine.name+" "+width+"px duration content is not clipped");assert.equal(layout.documentOverflow,0);assert.equal(layout.levelWhiteSpace,"nowrap");assert.equal(layout.psiWhiteSpace,"nowrap");
        assertProgressionLayout(await readSubclassProgressionLayout(page),engine.name+" "+width+"px");
      }
      await page.setViewportSize({width:412,height:915});await page.focus("#reference-show");await page.keyboard.press("Tab");
      assert.equal(await page.evaluate(()=>document.activeElement?.id),"reference-level",engine.name+" native filter keyboard order");
      await page.selectOption("#reference-show","common_features");await page.selectOption("#reference-level","3rd");
      const filtered=await page.evaluate(()=>{const table=document.querySelector<HTMLTableElement>("#psi-cost-reference-table")!,rows=[...table.querySelectorAll("tbody tr")];return{totalRows:rows.length,visibleRows:rows.filter(row=>getComputedStyle(row).display!=="none").length,headerDisplay:getComputedStyle(table.tHead!).display,count:document.querySelector("#reference-filter-count")?.textContent,noMatch:(document.querySelector("#reference-filter-no-matches") as HTMLElement).hidden,scrollable:table.scrollWidth>table.closest<HTMLElement>(".table-scroll")!.clientWidth,noForcedAriaHiding:rows.every(row=>!row.hasAttribute("aria-hidden"))};});
      assert.equal(filtered.totalRows,34);assert.equal(filtered.visibleRows,0);assert.equal(filtered.headerDisplay,"table-header-group");assert.equal(filtered.count,"Showing 0 of 34 features.");assert.equal(filtered.noMatch,false);assert.equal(filtered.scrollable,true);assert.equal(filtered.noForcedAriaHiding,true);
      await page.selectOption("#reference-show","");await page.selectOption("#reference-level","");await page.setViewportSize({width:1280,height:900});
      const desktopLayout=await page.evaluate(()=>{
        const table=document.querySelector<HTMLTableElement>("#psi-cost-reference-table")!,wrapper=table.closest<HTMLElement>(".table-scroll")!,wrapperRect=wrapper.getBoundingClientRect(),lastColumn=table.tHead!.rows[0]!.cells[5]!.getBoundingClientRect(),tableRect=table.getBoundingClientRect(),durationCells=[...table.tBodies[0]!.rows].map(row=>row.cells[5]!);wrapper.scrollLeft=0;
        return{tableWidth:tableRect.width,wrapperWidth:wrapper.clientWidth,scrollable:wrapper.scrollWidth>wrapper.clientWidth+1,lastColumnContained:lastColumn.left>=wrapperRect.left-1&&lastColumn.right<=wrapperRect.right+1,lastColumnRatio:lastColumn.width/tableRect.width,durationContentFits:durationCells.every(cell=>cell.scrollWidth<=cell.clientWidth+1&&cell.scrollHeight<=cell.clientHeight+1&&getComputedStyle(cell).textOverflow!=="ellipsis"),documentOverflow:document.documentElement.scrollWidth-document.documentElement.clientWidth,nameSelectFits:document.querySelector<HTMLElement>("#name-select")!.scrollWidth<=document.querySelector<HTMLElement>("#name-select")!.clientWidth+1,mainWidth:document.querySelector<HTMLElement>("main.layout")!.getBoundingClientRect().width};
      });
      assert.ok(desktopLayout.tableWidth<=desktopLayout.wrapperWidth+1,engine.name+" desktop table fits its wrapper");assert.equal(desktopLayout.scrollable,false,engine.name+" desktop table does not hide the duration column");assert.equal(desktopLayout.lastColumnContained,true,engine.name+" desktop duration column is visible");assert.ok(desktopLayout.lastColumnRatio>=.2,engine.name+" desktop duration column remains readable");assert.equal(desktopLayout.durationContentFits,true,engine.name+" desktop duration content is not clipped");assert.equal(desktopLayout.documentOverflow,0,engine.name+" desktop document overflow");assert.equal(desktopLayout.nameSelectFits,true,engine.name+" desktop Name control still fits");assert.ok(desktopLayout.mainWidth<=1217,engine.name+" Psi sizing remains table-local");
      assertProgressionLayout(await readSubclassProgressionLayout(page),engine.name+" desktop");
      await page.selectOption("#reference-show","common_features");await page.selectOption("#reference-level","3rd");await page.emulateMedia({media:"print"});await page.setViewportSize({width:1366,height:900});
      const printLayout=await page.evaluate(()=>{
        const table=document.querySelector<HTMLTableElement>("#entity-subclass_feature_reference .quick-reference-table")!,wrapper=table.closest<HTMLElement>(".table-scroll")!,wrapperRect=wrapper.getBoundingClientRect(),tableRect=table.getBoundingClientRect(),headers=[...table.querySelectorAll<HTMLTableCellElement>("th")],lastColumn=headers[5]!.getBoundingClientRect(),durationCells=[...table.tBodies[0]!.rows].map(row=>row.cells[5]!);
        return{overflowX:getComputedStyle(wrapper).overflowX,tableWidth:tableRect.width,wrapperWidth:wrapperRect.width,lastColumnContained:lastColumn.left>=wrapperRect.left-1&&lastColumn.right<=wrapperRect.right+1,lastColumnRatio:lastColumn.width/tableRect.width,durationContentFits:durationCells.every(cell=>cell.scrollWidth<=cell.clientWidth+1&&cell.scrollHeight<=cell.clientHeight+1&&getComputedStyle(cell).textOverflow!=="ellipsis"),documentOverflow:document.documentElement.scrollWidth-document.documentElement.clientWidth,rowDisplays:[...table.querySelectorAll("tbody tr")].map(row=>getComputedStyle(row).display),controlsDisplay:getComputedStyle(document.querySelector<HTMLElement>(".reference-filters")!).display};
      });
      assert.equal(printLayout.overflowX,"visible",engine.name+" print overflow");assert.ok(printLayout.tableWidth<=printLayout.wrapperWidth+1,engine.name+" print table width");assert.equal(printLayout.lastColumnContained,true,engine.name+" print Ongoing Duration column");assert.ok(printLayout.lastColumnRatio>=.22,engine.name+" print duration column remains readable");assert.equal(printLayout.durationContentFits,true,engine.name+" print duration content is not clipped");assert.equal(printLayout.documentOverflow,0,engine.name+" print document overflow");
      assert.equal(printLayout.rowDisplays.length,34);assert.ok(printLayout.rowDisplays.every(display=>display==="table-row"),engine.name+" print restores all rows");assert.equal(printLayout.controlsDisplay,"none",engine.name+" print hides table filters");
      assertProgressionLayout(await readSubclassProgressionLayout(page),engine.name+" print");
    }finally{await browser.close();}
  }
});

test("Manifested Strike progression cells render exactly in desktop browsers", async () => {
  const result = await executeBuild("prototype");
  const expectedCells = ["3–4", "1d6", "5–10", "1d8", "11–16", "1d10", "17–20", "1d12"];
  const expectedProse = "Manifested Strike die by level: 1d6 (3rd–4th) → 1d8 (5th–10th) → 1d10 (11th–16th) → 1d12 (17th–20th)";
  const url = `${pathToFileURL(result.htmlPath).href}#category=common_features&topic=common_features_common_manifested_strike_topic`;

  for (const engine of desktopBrowsers) {
    const browser = await engine.type.launch(browserLaunchOptions);
    const page = await browser.newPage({ viewport: { width: 1366, height: 768 } });
    try {
      await page.goto(url);
      const rendered = await page.evaluate(() => {
        const table = [...document.querySelectorAll("table")].find(candidate =>
          [...candidate.querySelectorAll("th")].map(cell => cell.textContent).join("|") === "Fighter Level|Manifested Strike Die"
        )!;
        const prose = [...document.querySelectorAll("article p")].find(paragraph =>
          paragraph.textContent?.startsWith("Manifested Strike die by level:")
        )!;
        return {
          cells: [...table.querySelectorAll("tbody td")].map(cell => ({ textContent: cell.textContent, innerHTML: cell.innerHTML })),
          prose: prose.textContent
        };
      });

      assert.deepEqual(rendered.cells.map(cell => cell.textContent), expectedCells, `${engine.name}: table cell text`);
      assert.ok(rendered.cells.every(cell => !cell.innerHTML.includes("�")), `${engine.name}: table markup must not contain U+FFFD`);
      assert.equal(rendered.prose, expectedProse, `${engine.name}: progression prose must remain unchanged`);
    } finally {
      await browser.close();
    }
  }
});

test("Example Play uses one flat, full-width row per discipline at every viewport", async () => {
  const result=await executeBuild("prototype");
  const base=pathToFileURL(result.htmlPath).href;
  const exampleUrl=base+"#category=common_features&topic=common_features_common_example_play_topic";
  const glacialUrl=base+"#category=common_features&topic=common_features_common_overload_topic";
  const viewports=[
    {name:"wide desktop",width:1600,height:1000},
    {name:"standard laptop",width:1366,height:900},
    {name:"narrow tablet",width:820,height:1180},
    {name:"mobile",width:390,height:844}
  ];
  const expectedHeadings=["Pyrokinesis","Psychokinesis","Cryokinesis","Electrokinesis"];
  let canonicalText:string[]|undefined;
  for(const engine of desktopBrowsers){
    const browser=await engine.type.launch(browserLaunchOptions);
    const page=await browser.newPage();
    try{
      for(const viewport of viewports){
        await page.setViewportSize(viewport);
        await page.goto(exampleUrl);
        const rendered=await page.evaluate(()=>{
          const article=document.querySelector<HTMLElement>("#entity-common_example_play")!;
          const container=article.querySelector<HTMLElement>(":scope > .example-play-flow")!;
          const containerRect=container.getBoundingClientRect();
          const sections=[...container.querySelectorAll<HTMLElement>(":scope > .example-play-section")];
          const rects=sections.map(section=>section.getBoundingClientRect());
          const contents=sections.map(section=>section.querySelector<HTMLElement>(".example-play-section__content")!);
          return{
            containerClass:container.className,
            containerDisplay:getComputedStyle(container).display,
            legacyLayoutCount:article.querySelectorAll(".example-play-sections,.example-play-section__card").length,
            count:sections.length,
            headings:sections.map(section=>section.querySelector("h3")?.textContent),
            texts:sections.map(section=>section.textContent??""),
            fullWidth:rects.every(rect=>Math.abs(rect.width-containerRect.width)<=1&&Math.abs(rect.left-containerRect.left)<=1),
            ownRows:rects.every((rect,index)=>index===0||rect.top>=rects[index-1]!.bottom),
            verticalSeparation:rects.every((rect,index)=>index===0||rect.top-rects[index-1]!.bottom>=20),
            aligned:sections.every((section,index)=>{
              const heading=section.querySelector<HTMLElement>(".example-play-section__heading")!.getBoundingClientRect();
              const content=contents[index]!.getBoundingClientRect();
              return Math.abs(heading.left-content.left)<=1&&Math.abs(heading.right-content.right)<=1;
            }),
            readableWidth:contents.every(content=>{
              const width=content.getBoundingClientRect().width;
              return width>=Math.min(containerRect.width,600)-1&&width<=containerRect.width+1;
            }),
            flat:contents.every(content=>{
              const style=getComputedStyle(content);
              return parseFloat(style.borderTopWidth)>0&&parseFloat(style.borderRightWidth)===0&&parseFloat(style.borderBottomWidth)===0&&parseFloat(style.borderLeftWidth)===0&&style.boxShadow==="none"&&parseFloat(style.borderRadius)===0;
            }),
            titlesFit:sections.every(section=>{
              const title=section.querySelector<HTMLElement>(".example-play-section__title")!;
              return title.scrollWidth<=title.clientWidth;
            }),
            phaseListCounts:sections.map(section=>section.querySelectorAll(".example-play-section__phase ol,.example-play-section__phase ul").length),
            semanticPhases:sections.every(section=>{const phases=[...section.querySelectorAll<HTMLElement>(".example-play-section__phase")];return phases.length===6&&phases.every(phase=>[...phase.children].slice(1).every(child=>child.tagName==="P"||child.tagName==="OL"||child.tagName==="UL"));}),
            listsContained:sections.every(section=>[...section.querySelectorAll<HTMLElement>("ol,ul,li")].every(element=>element.scrollWidth<=element.clientWidth+1)),
            contained:rects.every((rect,index)=>rect.left>=containerRect.left&&rect.right<=containerRect.right&&sections[index]!.scrollWidth<=sections[index]!.clientWidth),
            documentOverflow:document.documentElement.scrollWidth-document.documentElement.clientWidth
          };
        });
        const size=engine.name+" "+viewport.name+" "+viewport.width+"x"+viewport.height;
        assert.equal(rendered.containerClass,"example-play-flow",size+": semantic flow class");
        assert.equal(rendered.containerDisplay,"block",size+": block flow");
        assert.equal(rendered.legacyLayoutCount,0,size+": no grid/card classes");
        assert.equal(rendered.count,4,size+": section count");
        assert.deepEqual(rendered.headings,expectedHeadings,size+": heading order");
        canonicalText??=rendered.texts;
        assert.deepEqual(rendered.texts,canonicalText,size+": unchanged content and order");
        assert.equal(rendered.fullWidth,true,size+": each discipline occupies a full row");
        assert.equal(rendered.ownRows,true,size+": sections stack vertically");
        assert.equal(rendered.verticalSeparation,true,size+": sections have clear whitespace");
        assert.equal(rendered.aligned,true,size+": headings align with example content");
        assert.equal(rendered.readableWidth,true,size+": readable inner width");
        assert.equal(rendered.flat,true,size+": flat divider treatment");
        assert.equal(rendered.titlesFit,true,size+": titles wrap without overflow");
        assert.deepEqual(rendered.phaseListCounts,[5,6,6,6],size+": semantic phase-list counts");
        assert.equal(rendered.semanticPhases,true,size+": every phase renders only paragraph/list body blocks");
        assert.equal(rendered.listsContained,true,size+": example lists and labels remain contained");
        assert.equal(rendered.contained,true,size+": sections stay within the article");
        assert.equal(rendered.documentOverflow,0,size+": no horizontal page overflow");
        await page.goto(glacialUrl);
        const inline=page.locator("#entity-common_overload .inline-example");assert.equal(await inline.count(),1,size+": one Overload Glacial example");assert.equal(await inline.locator("h3").textContent(),"Example — Level 11 Cryokinesis (Proficiency Bonus 4, Intelligence +3)");const inlineList=await inline.evaluate(element=>{const lists=[...element.querySelectorAll<HTMLElement>(":scope > .inline-example__body > ul")];return{listCount:lists.length,itemCounts:lists.map(list=>list.querySelectorAll(":scope > li").length),contained:[...element.querySelectorAll<HTMLElement>("ul,li")].every(node=>node.scrollWidth<=node.clientWidth+1),documentOverflow:document.documentElement.scrollWidth-document.documentElement.clientWidth};});assert.deepEqual(inlineList.itemCounts,[3],size+": inline example list items");assert.equal(inlineList.listCount,1,size+": inline example semantic list");assert.equal(inlineList.contained,true,size+": inline example list containment");assert.equal(inlineList.documentOverflow,0,size+": inline example page overflow");assert.equal(await page.locator("#entity-common_example_play .inline-example").count(),0,size+": absent from Example Play");
      }
      await page.emulateMedia({media:"print"});
      await page.goto(exampleUrl);
      assert.equal(await page.locator(".example-play-section").first().evaluate(element=>getComputedStyle(element).breakInside),"avoid",engine.name+": print section break");
      assert.equal(await page.locator(".example-play-section").last().evaluate(element=>getComputedStyle(element).breakInside),"avoid",engine.name+": final print section break");
      await page.goto(glacialUrl);assert.equal(await page.locator(".inline-example").evaluate(element=>getComputedStyle(element).breakInside),"avoid",engine.name+": print inline break");
    }finally{
      await browser.close();
    }
  }
});


test("Rules area filtering is immediate, canonical, progressive, and history-safe on desktop and mobile",async()=>{
  const result=await executeBuild("prototype");const browser=await chromium.launch(browserLaunchOptions);
  const expected=["Telekinetic Shove — Psychokinesis","Vectored Thrust — Psychokinesis","Explosion/Implosion — Psychokinesis","Telekinetic Slam — Psychokinesis","Mass Levitation — Psychokinesis"];
  try{
    for(const viewport of [{width:1366,height:768},{width:390,height:844}]){
      const page=await browser.newPage({viewport});await page.goto(pathToFileURL(result.htmlPath).href+defaultReferenceFragment);
      const psychokinesis=page.locator(`input[data-facet="rules_area"][value="psychokinesis"]`),common=page.locator(`input[data-facet="rules_area"][value="common_features"]`);
      await psychokinesis.check();await page.locator(`#filter-root[data-filter-settled="true"]`).waitFor();
      const labels=()=>page.locator("#filter-results button").allTextContents();assert.deepEqual(await labels(),expected);assert.equal(await common.isChecked(),false);
      await common.check();const multiple=await labels();assert.equal(multiple.filter(label=>label==="Overload — Common Features").length,1);const firstPsychokinesis=multiple.findIndex(label=>label.endsWith("— Psychokinesis"));assert.ok(firstPsychokinesis>0);assert.ok(multiple.slice(0,firstPsychokinesis).every(label=>label.endsWith("— Common Features")));
      await page.goBack();assert.equal(await psychokinesis.isChecked(),true);assert.equal(await common.isChecked(),false);assert.deepEqual(await labels(),expected);
      await page.goForward();assert.equal(await psychokinesis.isChecked(),true);assert.equal(await common.isChecked(),true);assert.deepEqual(await labels(),multiple);
      await common.uncheck();assert.deepEqual(await labels(),expected);assert.ok(!(await labels()).some(label=>label.startsWith("Overload —")));await page.close();
    }
  }finally{await browser.close();}
});

test("concentration metadata ribbon wraps without overflow on desktop and mobile",async()=>{
  const result=await executeBuild("prototype");const url=`${pathToFileURL(result.htmlPath).href}#calculator&card=advanced_gravitic_press&level=20&modifier=5&group=advanced_training`;
  const browser=await chromium.launch(browserLaunchOptions);
  try{
    for(const viewport of [{width:1366,height:768},{width:390,height:844}]){
      const page=await browser.newPage({viewport});await page.goto(url);await page.waitForSelector("#calculator-feature-results .feature-metadata__item--concentration");
      const rendered=await page.evaluate(()=>{const metadata=document.querySelector<HTMLElement>("#calculator-feature-results .feature-metadata")!;const items=[...metadata.querySelectorAll<HTMLElement>(".feature-metadata__item")];const article=metadata.closest("article")!;const articleRect=article.getBoundingClientRect();const itemRects=items.map(item=>item.getBoundingClientRect());return{flexWrap:getComputedStyle(metadata).flexWrap,contained:metadata.scrollWidth<=metadata.clientWidth&&itemRects.every(rect=>rect.left>=articleRect.left&&rect.right<=articleRect.right),noOverlap:itemRects.every((rect,index)=>itemRects.slice(index+1).every(other=>rect.right<=other.left||other.right<=rect.left||rect.bottom<=other.top||other.bottom<=rect.top)),documentOverflow:document.documentElement.scrollWidth-document.documentElement.clientWidth,badgeText:metadata.querySelector(".feature-metadata__item--concentration dd")?.textContent,lineCount:new Set(itemRects.map(rect=>Math.round(rect.top))).size};});
      const size=`${viewport.width}x${viewport.height}`;
      assert.equal(rendered.flexWrap,"wrap",`${size}: metadata must support wrapping`);
      assert.equal(rendered.contained,true,`${size}: metadata items must stay inside the article`);
      assert.equal(rendered.noOverlap,true,`${size}: metadata items must not overlap`);
      assert.equal(rendered.documentOverflow,0,`${size}: page must not scroll horizontally`);
      assert.equal(rendered.badgeText,"Concentration",`${size}: badge text must remain visible`);
      if(viewport.width===390)assert.ok(rendered.lineCount>1,`${size}: metadata should wrap cleanly at the mobile width`);await page.close();
    }
  }finally{await browser.close();}
});


test("Calculator Feature Deck stays contained and operable on desktop and mobile",async()=>{
  const result=await executeBuild("prototype"),url=pathToFileURL(result.htmlPath).href+"#calculator&card=manifested_strike&level=3&modifier=2";
  for(const engine of desktopBrowsers){
    const browser=await engine.type.launch(browserLaunchOptions);
    try{
      for(const viewport of [{name:"desktop",width:1280,height:1000,columns:3},{name:"mobile",width:390,height:844,columns:1}] as const){
        const page=await browser.newPage({viewport});await page.goto(url);await page.waitForSelector("#calculator-root");const context=`${engine.name} ${viewport.name}`;
        const initial=await page.evaluate(()=>{const root=document.querySelector<HTMLElement>("#calculator-root")!,controls=root.querySelector<HTMLElement>(".calculator__controls")!,result=root.querySelector<HTMLElement>("#calculator-feature-results")!,rootRect=root.getBoundingClientRect(),fields=[...controls.querySelectorAll<HTMLElement>(":scope > .field")],fieldRects=fields.map(field=>field.getBoundingClientRect()),cards=[...root.querySelectorAll<HTMLElement>(".calculator__card")],containers=[controls,...cards,result,...result.querySelectorAll<HTMLElement>(".feature-metadata,.calculator__projection,.calculator__canonical-rules,.calculator__facts,.calculator__tiers,.calculator__tier")],contained=containers.every(element=>{const rect=element.getBoundingClientRect();return rect.left>=rootRect.left-1&&rect.right<=rootRect.right+1&&element.scrollWidth<=element.clientWidth+1;});return{selectIds:[...root.querySelectorAll<HTMLSelectElement>("select")].map(select=>select.id),columns:getComputedStyle(controls).gridTemplateColumns.trim().split(/\s+/).filter(Boolean).length,fieldTops:fieldRects.map(rect=>rect.top),fieldBottoms:fieldRects.map(rect=>rect.bottom),cardCount:cards.length,futureCount:cards.filter(card=>card.dataset.available==="false").length,selected:root.querySelector<HTMLElement>('.calculator__card[aria-pressed="true"]')?.dataset.cardId,heading:result.querySelector(":scope > h3")?.textContent,text:result.textContent??"",contained,documentOverflow:document.documentElement.scrollWidth-document.documentElement.clientWidth};});
        assert.deepEqual(initial.selectIds,["calculator-feature-group","calculator-level","calculator-psi-modifier"],context+" three controls");assert.equal(initial.columns,viewport.columns,context+" control columns");assert.equal(initial.cardCount,35,context+" full deck");assert.ok(initial.futureCount>0,context+" future cards visible");assert.equal(initial.selected,"manifested_strike",context+" default card");assert.equal(initial.heading,"Manifested Strike",context+" detail heading");assert.match(initial.text,/Hit:\s*1d20 \+ 5/u,context+" level 3 calculation");assert.equal(initial.contained,true,context+" contained");assert.equal(initial.documentOverflow,0,context+" no horizontal overflow");
        if(viewport.columns===3)assert.ok(Math.max(...initial.fieldTops)-Math.min(...initial.fieldTops)<=1,context+" controls share row");else for(let index=1;index<initial.fieldTops.length;index++)assert.ok(initial.fieldTops[index]!>=initial.fieldBottoms[index-1]!-1,context+" controls stack");
        await page.locator('.calculator__card[data-card-id="blood_tax"]').click();await page.waitForFunction(()=>document.querySelector("#calculator-feature-results > h3")?.textContent==="Blood Tax");const bloodTax3=await page.evaluate(()=>{const result=document.querySelector<HTMLElement>("#calculator-feature-results")!,tiers=[...result.querySelectorAll<HTMLElement>(".calculator__tier")],root=document.querySelector<HTMLElement>("#calculator-root")!,rootRect=root.getBoundingClientRect(),blocks=[result,...tiers,result.querySelector<HTMLElement>(".calculator__mastery")!,result.querySelector<HTMLElement>(".calculator__context")!];return{headings:tiers.map(tier=>tier.querySelector("h5")?.textContent),availability:tiers.map(tier=>tier.dataset.available),text:result.textContent??"",contained:blocks.every(element=>{const rect=element.getBoundingClientRect();return rect.left>=rootRect.left-1&&rect.right<=rootRect.right+1&&element.scrollWidth<=element.clientWidth+1;}),overflow:document.documentElement.scrollWidth-document.documentElement.clientWidth};});assert.deepEqual(bloodTax3.headings,["T0 — No Overload","T1 — Overload","T2 — Overload"],context+" Blood Tax tier cards");assert.deepEqual(bloodTax3.availability,["true","true","false"],context+" level 3 Blood Tax availability");assert.match(bloodTax3.text,/Available at Fighter level 10\./u,context+" level 3 T2 warning");assert.match(bloodTax3.text,/Available at Fighter level 18/u,context+" level 3 mastery warning");assert.equal(bloodTax3.contained,true,context+" Blood Tax containment");assert.equal(bloodTax3.overflow,0,context+" Blood Tax overflow");
        await page.selectOption("#calculator-level","10");assert.deepEqual(await page.locator(".calculator__tier").evaluateAll(tiers=>tiers.map(tier=>(tier as HTMLElement).dataset.available)),["true","true","true"],context+" level 10 Blood Tax availability");assert.doesNotMatch((await page.locator('.calculator__tier[data-tier="2"]').textContent())??"",/Available at Fighter level/u,context+" level 10 T2 warning removed");await page.selectOption("#calculator-level","18");const bloodTax18=await page.locator("#calculator-feature-results").textContent();assert.match(bloodTax18??"",/With Overload Mastery:\s*3 HP/u,context+" level 18 T1 reduction");assert.match(bloodTax18??"",/With Overload Mastery:\s*6 HP/u,context+" level 18 T2 reduction");assert.match(bloodTax18??"",/Blood Tax divisor:\s*2/u,context+" level 18 divisor");assert.match(bloodTax18??"",/Minimum per Overload:\s*1 HP/u,context+" level 18 minimum");
        await page.locator('.calculator__card[data-card-id="advanced_inner_reserve"]').click();await page.waitForFunction(()=>document.querySelector("#calculator-feature-results > h3")?.textContent==="Inner Reserve");assert.match(new URL(page.url()).hash,/card=advanced_inner_reserve/u);assert.equal(await page.locator("#calculator-feature-results > h3").evaluate(element=>document.activeElement===element),true,context+" selected detail focus");
        await page.selectOption("#calculator-level","20");await page.selectOption("#calculator-psi-modifier","5");const updated=await page.locator("#calculator-feature-results").textContent();assert.match(updated??"",/Maximum Psi Points with Inner Reserve:\s*20/u,context+" live projection");assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth),0,context+" updated overflow");await page.close();
      }
    }finally{await browser.close();}
  }
});

test("Start Here is a contained single-column experience across engines, breakpoints, input, forced colors, reduced motion, and print",async()=>{
  const result=await executeBuild("prototype"),base=pathToFileURL(result.htmlPath).href,homeUrl=base+"#home";
  const widths=[320,412,760,761,1280,1366];
  for(const engine of desktopBrowsers){
    const browser=await engine.type.launch(browserLaunchOptions);
    const page=await browser.newPage({viewport:{width:1366,height:1000}});
    try{
      await page.goto(homeUrl);assert.equal(await page.evaluate(()=>document.activeElement===document.body),true,engine.name+" initial focus");
      for(const width of widths){
        await page.setViewportSize({width,height:1000});
        const observed=await page.evaluate(()=>{
          const main=document.querySelector<HTMLElement>("main.layout")!,content=document.querySelector<HTMLElement>("#rules-content")!,guide=document.querySelector<HTMLElement>('.home-guide[data-onboarding-id="start_here"]')!,controls=document.querySelector<HTMLElement>(".controls")!,nav=document.querySelector<HTMLElement>(".view-nav")!;
          const mainRect=main.getBoundingClientRect(),contentRect=content.getBoundingClientRect(),guideRect=guide.getBoundingClientRect(),navRect=nav.getBoundingClientRect(),gridColumns=getComputedStyle(main).gridTemplateColumns.trim().split(/\s+/).filter(Boolean);
          const blocks=[...guide.querySelectorAll<HTMLElement>("h2,h3,h4,p,li,dd,button")].filter(element=>getComputedStyle(element).display!=="none");
          return{
            view:main.dataset.view,homeClass:main.classList.contains("layout--home"),controlsHidden:controls.hidden,controlsDisplay:getComputedStyle(controls).display,
            gridColumnCount:gridColumns.length,contentContained:contentRect.left>=mainRect.left-1&&contentRect.right<=mainRect.right+1,guideContained:guideRect.left>=contentRect.left-1&&guideRect.right<=contentRect.right+1,
            guideWidth:guideRect.width,textContained:blocks.every(element=>element.scrollWidth<=element.clientWidth+1),documentOverflow:document.documentElement.scrollWidth-document.documentElement.clientWidth,
            navContained:navRect.left>=-1&&navRect.right<=innerWidth+1,navContentContained:nav.scrollWidth<=nav.clientWidth+1,
            pageHeading:guide.querySelector(":scope > h2")?.textContent,sectionCount:guide.querySelectorAll(":scope > .home-section").length,cardCount:guide.querySelectorAll(".home-card-list .home-card").length
          };
        });
        const context=`${engine.name} ${width}px`;
        assert.equal(observed.view,"home",context+" view");assert.equal(observed.homeClass,true,context+" home class");assert.equal(observed.controlsHidden,true,context+" native control hiding");assert.equal(observed.controlsDisplay,"none",context+" hidden controls layout");
        assert.equal(observed.gridColumnCount,1,context+" single grid column");assert.equal(observed.contentContained,true,context+" content in main");assert.equal(observed.guideContained,true,context+" guide in content");assert.equal(observed.textContained,true,context+" text containment");assert.equal(observed.documentOverflow,0,context+" document overflow");
        assert.equal(observed.navContained,true,context+" view navigation viewport containment");assert.equal(observed.navContentContained,true,context+" view navigation content containment");assert.equal(observed.pageHeading,"Start Here",context+" page heading");assert.equal(observed.sectionCount,5,context+" section count");assert.equal(observed.cardCount,4,context+" Discipline card count");
        if(width>=1280)assert.ok(observed.guideWidth<=900,context+" comfortable reading width");
      }

      await page.setViewportSize({width:412,height:915});await page.goto(homeUrl);
      await page.keyboard.press("Tab");assert.equal(await page.evaluate(()=>document.activeElement?.classList.contains("skip")),true,engine.name+" skip link first");
      const homeSkipBefore=await page.evaluate(()=>({hash:location.hash,length:history.length}));await page.keyboard.press("Enter");
      const homeSkipAfter=await page.evaluate(()=>({hash:location.hash,length:history.length,view:document.querySelector<HTMLElement>("main.layout")?.dataset.view,active:document.activeElement?.id}));
      assert.deepEqual(homeSkipAfter,{...homeSkipBefore,view:"home",active:"rules-content"},engine.name+" home skip link preserves route and history");
      await page.focus(".skip");
      assert.equal(await page.evaluate(()=>document.activeElement?.classList.contains("skip")),true,engine.name+" skip link can regain focus after activation");
      await page.keyboard.press("Tab");assert.equal(await page.evaluate(()=>document.activeElement?.id),"view-start-here",engine.name+" Start Here view control order");
      await page.keyboard.press("Tab");assert.equal(await page.evaluate(()=>document.activeElement?.id),"view-rules-reference",engine.name+" Rules Reference view control order");
      await page.keyboard.press("Tab");assert.equal(await page.evaluate(()=>document.activeElement?.id),"view-calculator",engine.name+" Calculator view control order");
      await page.keyboard.press("Tab");assert.equal(await page.evaluate(()=>document.activeElement?.getAttribute("data-onboarding-link-id")),"start_blood_tax",engine.name+" dedicated Blood Tax control follows view navigation");
      await page.keyboard.press("Tab");assert.equal(await page.evaluate(()=>document.activeElement?.getAttribute("data-onboarding-link-id")),"primary_build",engine.name+" hidden reference controls skipped");
      const focusStyle=await page.evaluate(()=>{const style=getComputedStyle(document.activeElement as Element);return{outlineStyle:style.outlineStyle,outlineWidth:parseFloat(style.outlineWidth)};});
      assert.notEqual(focusStyle.outlineStyle,"none",engine.name+" visible keyboard focus style");assert.ok(focusStyle.outlineWidth>0,engine.name+" visible keyboard focus width");
      await page.keyboard.press("Enter");
      const buildFocus=await page.evaluate(()=>{const heading=document.querySelector<HTMLElement>("#build_checklist_heading")!,rect=heading.getBoundingClientRect();return{active:document.activeElement===heading,visible:rect.top>=-1&&rect.bottom<=innerHeight+1};});
      assert.equal(buildFocus.active,true,engine.name+" Build path focus");assert.equal(buildFocus.visible,true,engine.name+" Build path reveal");

      await page.emulateMedia({forcedColors:"active"});await page.focus('[data-onboarding-link-id="primary_basic_turn"]');
      const forced=await page.evaluate(()=>{const control=document.activeElement as HTMLElement,card=document.querySelector<HTMLElement>(".home-card")!,style=getComputedStyle(control),cardStyle=getComputedStyle(card);return{query:matchMedia("(forced-colors: active)").matches,outlineStyle:style.outlineStyle,outlineWidth:parseFloat(style.outlineWidth),cardBorderStyle:cardStyle.borderTopStyle,cardBorderWidth:parseFloat(cardStyle.borderTopWidth)};});
      assert.equal(forced.query,true,engine.name+" forced-colors media");assert.notEqual(forced.outlineStyle,"none",engine.name+" forced-colors focus");assert.ok(forced.outlineWidth>0,engine.name+" forced-colors outline");assert.notEqual(forced.cardBorderStyle,"none",engine.name+" forced-colors card boundary");assert.ok(forced.cardBorderWidth>0,engine.name+" forced-colors card border");

      await page.emulateMedia({forcedColors:"none",reducedMotion:"reduce"});
      const reduced=await page.evaluate(()=>{const guide=document.querySelector<HTMLElement>(".home-guide")!,styles=[...guide.querySelectorAll<HTMLElement>("*")].map(element=>getComputedStyle(element));return{query:matchMedia("(prefers-reduced-motion: reduce)").matches,scrollBehavior:getComputedStyle(document.documentElement).scrollBehavior,noAnimations:styles.every(style=>style.animationDuration==="0s"||style.animationDuration===""),noTransitions:styles.every(style=>style.transitionDuration==="0s"||style.transitionDuration==="")};});
      assert.equal(reduced.query,true,engine.name+" reduced-motion media");assert.equal(reduced.scrollBehavior,"auto",engine.name+" reduced-motion scrolling");assert.equal(reduced.noAnimations,true,engine.name+" reduced-motion animations");assert.equal(reduced.noTransitions,true,engine.name+" reduced-motion transitions");

      await page.emulateMedia({media:"print",reducedMotion:"no-preference"});await page.setViewportSize({width:1366,height:1000});
      const printed=await page.evaluate(()=>{
        const guide=document.querySelector<HTMLElement>(".home-guide")!,sections=[...guide.querySelectorAll<HTMLElement>(".home-section")];
        return{navDisplay:getComputedStyle(document.querySelector<HTMLElement>(".view-nav")!).display,primaryDisplay:getComputedStyle(document.querySelector<HTMLElement>(".home-primary-paths")!).display,controlsDisplay:getComputedStyle(document.querySelector<HTMLElement>(".controls")!).display,guideDisplay:getComputedStyle(guide).display,documentOverflow:document.documentElement.scrollWidth-document.documentElement.clientWidth,sectionsAvoidBreaks:sections.every(section=>getComputedStyle(section).breakInside==="avoid")};
      });
      assert.equal(printed.navDisplay,"none",engine.name+" print view navigation");assert.equal(printed.primaryDisplay,"none",engine.name+" print primary navigation");assert.equal(printed.controlsDisplay,"none",engine.name+" print reference controls");assert.notEqual(printed.guideDisplay,"none",engine.name+" print onboarding content");assert.equal(printed.documentOverflow,0,engine.name+" print overflow");assert.equal(printed.sectionsAvoidBreaks,true,engine.name+" print section breaks");

      await page.emulateMedia({media:"screen",forcedColors:"none",reducedMotion:"no-preference"});await page.click("#view-rules-reference");await page.waitForSelector("#entity-how_to_play");
      assert.equal(await page.locator("main.layout").getAttribute("data-view"),"reference",engine.name+" Rules Reference activation");assert.equal(await page.locator(".controls").isVisible(),true,engine.name+" reference controls restored");assert.equal(await page.locator("#entity-how_to_play h2").textContent(),"How to Play This Subclass",engine.name+" default reference topic");
      const referenceSkipBefore=await page.evaluate(()=>({hash:location.hash,length:history.length}));await page.focus(".skip");await page.keyboard.press("Enter");
      const referenceSkipAfter=await page.evaluate(()=>({hash:location.hash,length:history.length,view:document.querySelector<HTMLElement>("main.layout")?.dataset.view,active:document.activeElement?.id,heading:document.querySelector("#entity-how_to_play h2")?.textContent}));
      assert.deepEqual(referenceSkipAfter,{...referenceSkipBefore,view:"reference",active:"rules-content",heading:"How to Play This Subclass"},engine.name+" reference skip link preserves route and history");
      await page.click("#view-start-here");assert.equal(await page.locator("main.layout").getAttribute("data-view"),"home",engine.name+" Start Here return");assert.equal(await page.evaluate(()=>document.activeElement?.id),"start_here_heading",engine.name+" Start Here return focus");
    }finally{await browser.close();}
  }
});
