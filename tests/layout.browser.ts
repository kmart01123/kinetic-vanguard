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

test("example turns remain distinct and contained on desktop and mobile in both browsers", async () => {
  const result = await executeBuild("prototype");
  const url = `${pathToFileURL(result.htmlPath).href}#category=common_features&topic=common_features_common_overload_topic`;
  const viewports = [{ width: 1366, height: 900 }, { width: 390, height: 844 }];

  for (const engine of desktopBrowsers) {
    const browser = await engine.type.launch({ headless: true });
    const page = await browser.newPage();
    try {
      for (const viewport of viewports) {
        await page.setViewportSize(viewport);await page.goto(url);
        const rendered = await page.evaluate(() => {
          const article = document.querySelector<HTMLElement>("article")!;const articleRect = article.getBoundingClientRect();const section=document.querySelector<HTMLElement>(".example-turns")!;const examples = [...document.querySelectorAll<HTMLElement>(".example-turn")];const tiers=[...document.querySelectorAll<HTMLElement>(".feature-tier")];const articleHeading=article.querySelector<HTMLElement>("h2")!;
          return {
            count:examples.length,
            heading:section.querySelector(".example-turns__heading")?.textContent,
            titles:examples.map(example=>example.querySelector(".example-turn__title")?.textContent),
            phases:examples.map(example=>[...example.querySelectorAll(".example-turn__phase-title")].map(label=>label.textContent)),
            contained:examples.every(example=>{const rect=example.getBoundingClientRect();return rect.left>=articleRect.left&&rect.right<=articleRect.right&&example.scrollWidth<=example.clientWidth;}),
            styled:examples.every(example=>{const style=getComputedStyle(example);return style.backgroundColor!=="rgba(0, 0, 0, 0)"&&parseFloat(style.borderInlineStartWidth)>0;}),
            tierCount:tiers.length,
            tierLabels:tiers.map(tier=>tier.querySelector(".feature-tier__label")?.textContent),
            tiersContained:tiers.every(tier=>{const rect=tier.getBoundingClientRect();return rect.left>=articleRect.left&&rect.right<=articleRect.right&&tier.scrollWidth<=tier.clientWidth;}),
            tiersStyled:tiers.every(tier=>{const label=tier.querySelector<HTMLElement>(".feature-tier__label")!;const body=tier.querySelector<HTMLElement>(".feature-tier__content p")!;const style=getComputedStyle(label);return style.backgroundColor!=="rgba(0, 0, 0, 0)"&&parseFloat(style.borderInlineStartWidth)>0&&Number(style.fontWeight)>Number(getComputedStyle(body).fontWeight)&&parseFloat(style.fontSize)<parseFloat(getComputedStyle(articleHeading).fontSize);}),
            documentOverflow:document.documentElement.scrollWidth-document.documentElement.clientWidth
          };
        });
        const size=`${engine.name} ${viewport.width}x${viewport.height}`;assert.equal(rendered.count,4,`${size}: example count`);assert.equal(rendered.heading,"Example Turns",`${size}: section heading`);assert.deepEqual(rendered.titles,["Glacial Spike Tier 2 Lockdown — Level 11 Cryokinesis","Focused Fire — Full Attack Turn, Level 11 Pyrokinesis","Aerial Repositioning — Sustained Turn, Level 11 Psychokinesis","Frozen-Ground Lockdown — Level 11 Cryokinesis"],`${size}: ordered titles`);assert.ok(rendered.phases.every(labels=>labels.join("|")==="Setup|Activation|Rolls and saves|Damage|Effects|Result"),`${size}: complete phases`);assert.equal(rendered.contained,true,`${size}: examples must stay within the article`);assert.equal(rendered.styled,true,`${size}: examples need a distinct background and border`);assert.equal(rendered.tierCount,2,`${size}: tier count`);assert.deepEqual(rendered.tierLabels,["T1 Overload","T2 Overload"],`${size}: tier labels`);assert.equal(rendered.tiersContained,true,`${size}: tiers must stay within the article`);assert.equal(rendered.tiersStyled,true,`${size}: tier labels must be distinct and subordinate`);assert.equal(rendered.documentOverflow,0,`${size}: page must not scroll horizontally`);
      }
      await page.emulateMedia({media:"print"});await page.goto(url);assert.equal(await page.locator(".example-turn").first().evaluate(element=>getComputedStyle(element).breakInside),"avoid",`${engine.name}: print examples should avoid internal breaks`);
    } finally {
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
