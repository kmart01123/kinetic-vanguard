import assert from "node:assert/strict";
import test from "node:test";
import { pathToFileURL } from "node:url";
import { chromium, firefox } from "playwright";
import { executeBuild } from "../src/build.js";
import { loadAuthority } from "../src/load.js";

const desktopViewports = [
  { width: 1640, height: 860 },
  { width: 1440, height: 900 },
  { width: 1366, height: 768 },
  { width: 1280, height: 800 },
  { width: 1024, height: 768 }
];
const desktopBrowsers = [
  { name: "Chromium", type: chromium },
  { name: "Firefox", type: firefox }
];
const nativeSelectIndicatorAllowance = 24;

test("master Name select renders canonical progression and stable renamed routes in Chromium and Firefox",async()=>{
  const result=await executeBuild("prototype");const {authority}=await loadAuthority();const url=pathToFileURL(result.htmlPath).href;
  const rulesAreas=authority.vocabularies.rules_areas!;const expectedGroups=[...rulesAreas].sort((a,b)=>a.order-b.order).map(area=>area.label);
  const featureIds=new Set(authority.entities.filter(entity=>entity.kind==="feature").map(entity=>entity.id));
  const expectedFeatures=Object.fromEntries(rulesAreas.map(area=>[area.label,authority.entities.filter(entity=>entity.kind==="feature"&&entity.presentation_metadata.primary_rules_area===area.id).sort((a,b)=>Number(a.level)-Number(b.level)||(a.title<b.title?-1:a.title>b.title?1:0)||(a.id<b.id?-1:a.id>b.id?1:0)).map(entity=>entity.id)]));
  for(const engine of desktopBrowsers){
    const browser=await engine.type.launch({headless:true});
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
      for(const [id,title,topic] of [["advanced_deflection_screen","Deflection Screen","advanced_training_advanced_deflection_screen_topic"],["advanced_phase_step","Phase Step","advanced_training_advanced_phase_step_topic"]] as const){
        const historyBefore=await page.evaluate(()=>(window as any).__namePushCount);await page.selectOption("#name-select",id);
        assert.equal(new URL(page.url()).hash.includes(`entity=${id}`),true);assert.equal(new URLSearchParams(new URL(page.url()).hash.slice(1)).get("topic"),topic);assert.equal(await page.locator(`#entity-${id} h2`).textContent(),title);
        assert.equal(await page.locator("#name-select").inputValue(),id);assert.equal(await page.locator("#name-open").count(),0);assert.equal(await page.evaluate(()=>(window as any).__namePushCount),historyBefore+1);
        await page.selectOption("#name-select",id);assert.equal(await page.evaluate(()=>(window as any).__namePushCount),historyBefore+1,engine.name+" same selection history");
        await page.goBack();await page.goForward();assert.equal(await page.locator(`#entity-${id} h2`).textContent(),title,engine.name+" Forward navigation");await page.goBack();
      }
      await page.close();
    }finally{await browser.close();}
  }
});

test("mobile Category, Topic, Name, and result navigation focus and reveal the selected rule",async()=>{
  const result=await executeBuild("prototype");const url=pathToFileURL(result.htmlPath).href;
  for(const engine of desktopBrowsers){
    const browser=await engine.type.launch({headless:true});
    try{
      const page=await browser.newPage({viewport:{width:412,height:915}});await page.goto(url);
      const assertFocusedAndVisible=async(id:string)=>{
        await page.waitForFunction(entityId=>{const heading=document.querySelector<HTMLElement>("#entity-"+entityId+" h2");if(!heading)return false;const rect=heading.getBoundingClientRect();return document.activeElement===heading&&rect.top>=-1&&rect.bottom<=innerHeight+1;},id);
      };
      await page.selectOption("#category-select","psychokinesis");await assertFocusedAndVisible("telekinetic_shove");
      await page.selectOption("#topic-select","psychokinesis_mass_levitation_topic");await assertFocusedAndVisible("mass_levitation");
      await page.selectOption("#name-select","ball_lightning");await assertFocusedAndVisible("ball_lightning");
      await page.goto(url);await page.locator('input[data-facet="rules_area"][value="electrokinesis"]').check();await page.getByRole("button",{name:"Ball Lightning — Electrokinesis"}).click();await assertFocusedAndVisible("ball_lightning");
      assert.equal(new URLSearchParams(new URL(page.url()).hash.slice(1)).get("entity"),"ball_lightning");
    }finally{await browser.close();}
  }
});

test("prototype columns and long selected topics fit in desktop browsers", async () => {
  const result = await executeBuild("prototype");
  const url = `${pathToFileURL(result.htmlPath).href}#category=advanced_training&topic=advanced_training_advanced_deflection_screen_topic`;

  for (const engine of desktopBrowsers) {
    const browser = await engine.type.launch({ headless: true });
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
        assert.equal(layout.selectedTopic, "Deflection Screen");
        assert.equal(layout.selectedTopicFits, true, `${size}: selected Topic text must fit beside the native indicator`);
      }
    } finally {
      await browser.close();
    }
  }
});

test("prototype deliberately stacks below the two-column breakpoint", async () => {
  const result = await executeBuild("prototype");
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 760, height: 900 } });

  try {
    await page.goto(pathToFileURL(result.htmlPath).href);
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

test("Psi Cost Reference scrolls on mobile and fits every column in print",async()=>{
  const result=await executeBuild("prototype");const url=pathToFileURL(result.htmlPath).href+"#category=common_features&topic=common_features_subclass_feature_reference_topic";
  for(const engine of desktopBrowsers){
    const browser=await engine.type.launch({headless:true});
    try{
      const page=await browser.newPage({viewport:{width:412,height:915}});await page.goto(url);
      const layout=await page.evaluate(()=>{const table=[...document.querySelectorAll("table")].find(candidate=>[...candidate.querySelectorAll("th")].some(cell=>cell.textContent==="Ongoing Duration"));const wrapper=table?.closest(".table-scroll");if(!table||!wrapper)return null;const style=getComputedStyle(wrapper);const firstRow=table.querySelector("tbody tr")!;return{headers:[...table.querySelectorAll("th")].map(cell=>cell.textContent),tableClass:table.className,wrapperTabIndex:wrapper.getAttribute("tabindex"),overflowX:style.overflowX,scrollable:table.scrollWidth>wrapper.clientWidth,documentOverflow:document.documentElement.scrollWidth-document.documentElement.clientWidth,levelWhiteSpace:getComputedStyle(firstRow.children.item(0)!).whiteSpace,psiWhiteSpace:getComputedStyle(firstRow.children.item(3)!).whiteSpace};});
      assert.ok(layout,engine.name+" reference table");assert.deepEqual(layout.headers,["Level","Feature","Discipline","Psi","Activation","Ongoing Duration"]);assert.equal(layout.tableClass,"quick-reference-table");assert.equal(layout.wrapperTabIndex,"0");assert.ok(["auto","scroll"].includes(layout.overflowX));assert.equal(layout.scrollable,true);assert.equal(layout.documentOverflow,0);assert.equal(layout.levelWhiteSpace,"nowrap");assert.equal(layout.psiWhiteSpace,"nowrap");
      await page.focus("#reference-show");await page.keyboard.press("Tab");
      assert.equal(await page.evaluate(()=>document.activeElement?.id),"reference-level",engine.name+" native filter keyboard order");
      await page.selectOption("#reference-show","common_features");await page.selectOption("#reference-level","3rd");
      const filtered=await page.evaluate(()=>{const table=document.querySelector<HTMLTableElement>("#psi-cost-reference-table")!,rows=[...table.querySelectorAll("tbody tr")];return{totalRows:rows.length,visibleRows:rows.filter(row=>getComputedStyle(row).display!=="none").length,headerDisplay:getComputedStyle(table.tHead!).display,count:document.querySelector("#reference-filter-count")?.textContent,noMatch:(document.querySelector("#reference-filter-no-matches") as HTMLElement).hidden,scrollable:table.scrollWidth>table.closest<HTMLElement>(".table-scroll")!.clientWidth,noForcedAriaHiding:rows.every(row=>!row.hasAttribute("aria-hidden"))};});
      assert.equal(filtered.totalRows,34);assert.equal(filtered.visibleRows,0);assert.equal(filtered.headerDisplay,"table-header-group");assert.equal(filtered.count,"Showing 0 of 34 features.");assert.equal(filtered.noMatch,false);assert.equal(filtered.scrollable,true);assert.equal(filtered.noForcedAriaHiding,true);
      await page.emulateMedia({media:"print"});await page.setViewportSize({width:1366,height:900});
      const printLayout=await page.evaluate(()=>{const table=document.querySelector<HTMLElement>("#entity-subclass_feature_reference .quick-reference-table")!,wrapper=table.closest<HTMLElement>(".table-scroll")!,wrapperRect=wrapper.getBoundingClientRect(),lastColumn=table.querySelector("th:last-child")!.getBoundingClientRect();return{overflowX:getComputedStyle(wrapper).overflowX,tableWidth:table.getBoundingClientRect().width,wrapperWidth:wrapperRect.width,lastColumnContained:lastColumn.left>=wrapperRect.left&&lastColumn.right<=wrapperRect.right,documentOverflow:document.documentElement.scrollWidth-document.documentElement.clientWidth,rowDisplays:[...table.querySelectorAll("tbody tr")].map(row=>getComputedStyle(row).display),controlsDisplay:getComputedStyle(document.querySelector<HTMLElement>(".reference-filters")!).display};});
      assert.equal(printLayout.overflowX,"visible",engine.name+" print overflow");assert.ok(printLayout.tableWidth<=printLayout.wrapperWidth+1,engine.name+" print table width");assert.equal(printLayout.lastColumnContained,true,engine.name+" print Ongoing Duration column");assert.equal(printLayout.documentOverflow,0,engine.name+" print document overflow");
      assert.equal(printLayout.rowDisplays.length,34);assert.ok(printLayout.rowDisplays.every(display=>display==="table-row"),engine.name+" print restores all rows");assert.equal(printLayout.controlsDisplay,"none",engine.name+" print hides table filters");
    }finally{await browser.close();}
  }
});

test("Manifested Strike progression cells render exactly in desktop browsers", async () => {
  const result = await executeBuild("prototype");
  const expectedCells = ["3–4", "1d6", "5–10", "1d8", "11–16", "1d10", "17–20", "1d12"];
  const expectedProse = "Manifested Strike die by level: 1d6 (3rd–4th) → 1d8 (5th–10th) → 1d10 (11th–16th) → 1d12 (17th–20th)";
  const url = `${pathToFileURL(result.htmlPath).href}#category=common_features&topic=common_features_common_manifested_strike_topic`;

  for (const engine of desktopBrowsers) {
    const browser = await engine.type.launch({ headless: true });
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
    const browser=await engine.type.launch({headless:true});
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
        assert.equal(rendered.contained,true,size+": sections stay within the article");
        assert.equal(rendered.documentOverflow,0,size+": no horizontal page overflow");
        await page.goto(glacialUrl);
        const inline=page.locator("#entity-common_overload .inline-example");assert.equal(await inline.count(),1,size+": one Overload Glacial example");assert.equal(await inline.locator("h3").textContent(),"Example — Level 11 Cryokinesis (Proficiency Bonus 4, Intelligence +3)");assert.equal(await page.locator("#entity-common_example_play .inline-example").count(),0,size+": absent from Example Play");
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
  const result=await executeBuild("prototype");const browser=await chromium.launch({headless:true});
  const expected=["Telekinetic Shove — Psychokinesis","Vectored Thrust — Psychokinesis","Explosion/Implosion — Psychokinesis","Telekinetic Slam — Psychokinesis","Mass Levitation — Psychokinesis"];
  try{
    for(const viewport of [{width:1366,height:768},{width:390,height:844}]){
      const page=await browser.newPage({viewport});await page.goto(pathToFileURL(result.htmlPath).href);
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
  const result=await executeBuild("prototype");const url=`${pathToFileURL(result.htmlPath).href}#category=advanced_training&topic=advanced_training_advanced_gravitic_press_topic`;
  const browser=await chromium.launch({headless:true});
  try{
    for(const viewport of [{width:1366,height:768},{width:390,height:844}]){
      const page=await browser.newPage({viewport});await page.goto(url);await page.waitForSelector("#entity-advanced_gravitic_press .feature-metadata__item--concentration");
      const rendered=await page.evaluate(()=>{const metadata=document.querySelector<HTMLElement>("#entity-advanced_gravitic_press .feature-metadata")!;const items=[...metadata.querySelectorAll<HTMLElement>(".feature-metadata__item")];const article=metadata.closest("article")!;const articleRect=article.getBoundingClientRect();const itemRects=items.map(item=>item.getBoundingClientRect());return{flexWrap:getComputedStyle(metadata).flexWrap,contained:metadata.scrollWidth<=metadata.clientWidth&&itemRects.every(rect=>rect.left>=articleRect.left&&rect.right<=articleRect.right),noOverlap:itemRects.every((rect,index)=>itemRects.slice(index+1).every(other=>rect.right<=other.left||other.right<=rect.left||rect.bottom<=other.top||other.bottom<=rect.top)),documentOverflow:document.documentElement.scrollWidth-document.documentElement.clientWidth,badgeText:metadata.querySelector(".feature-metadata__item--concentration dd")?.textContent,lineCount:new Set(itemRects.map(rect=>Math.round(rect.top))).size};});
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
