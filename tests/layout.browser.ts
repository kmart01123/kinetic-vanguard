import assert from "node:assert/strict";
import test from "node:test";
import { pathToFileURL } from "node:url";
import { chromium, firefox } from "playwright";
import { executeBuild } from "../src/build.js";

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
        assert.equal(layout.selectedTopic, "Advanced Training I: Deflection Screen");
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
          [...candidate.querySelectorAll("th")].map(cell => cell.textContent).join("|") === "Fighter Level|MS Die"
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
  const expectedHeadings=["Cryokinesis","Pyrokinesis","Psychokinesis"];
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
        assert.equal(rendered.count,3,size+": section count");
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
        const inline=await page.evaluate(()=>{
          const article=document.querySelector<HTMLElement>("#entity-common_overload")!;
          const example=article.querySelector<HTMLElement>(".inline-example")!;
          const articleRect=article.getBoundingClientRect(),rect=example.getBoundingClientRect(),style=getComputedStyle(example);
          return{count:article.querySelectorAll(".inline-example").length,tier:example.dataset.overloadTier,absentFromExamplePlay:document.querySelector("#entity-common_example_play .inline-example")===null,contained:rect.left>=articleRect.left&&rect.right<=articleRect.right&&example.scrollWidth<=example.clientWidth,styled:style.backgroundColor!=="rgba(0, 0, 0, 0)"&&parseFloat(style.borderInlineStartWidth)>0,overflow:document.documentElement.scrollWidth-document.documentElement.clientWidth};
        });
        assert.deepEqual(inline,{count:1,tier:"2",absentFromExamplePlay:true,contained:true,styled:true,overflow:0},size+": inline Glacial example");
      }
      await page.emulateMedia({media:"print"});
      await page.goto(exampleUrl);
      assert.equal(await page.locator(".example-play-section").first().evaluate(element=>getComputedStyle(element).breakInside),"avoid",engine.name+": print section break");
      await page.goto(glacialUrl);
      assert.equal(await page.locator(".inline-example").evaluate(element=>getComputedStyle(element).breakInside),"avoid",engine.name+": print inline break");
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
