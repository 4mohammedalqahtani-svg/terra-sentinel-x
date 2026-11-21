// Guided tour (Arabic) for presenting the explorer. It only drives the page
// through its public controls, so it needs no hooks inside app.js.
(() => {
  const $ = (id) => document.getElementById(id);
  const q = (selector) => document.querySelector(selector);

  const setReveal = (on) => {
    const button = $("reveal");
    if (!button.disabled && (button.getAttribute("aria-pressed") === "true") !== on) button.click();
  };
  const setToggle = (id, on) => {
    const box = $(id);
    if (box.disabled || box.checked === on) return;
    box.checked = on;
    box.dispatchEvent(new Event("change", { bubbles: true }));
  };
  const closePopup = () => q("#map .leaflet-popup-close-button")?.click();
  const inspectFirstArea = () => {
    const region = $("region");
    if (!region.value) {
      const first = [...region.options].find((option) => option.value);
      if (!first) return;
      region.value = first.value;
      region.dispatchEvent(new Event("change", { bubbles: true }));
    }
    $("show-evidence").click();
  };

  let sliderAnimation;
  const stopSlider = () => cancelAnimationFrame(sliderAnimation);
  const demoSlider = () => {
    const slider = $("slider");
    const start = performance.now();
    const frames = [50, 15, 85, 50];
    const step = 1100;
    const tick = (now) => {
      const t = (now - start) / step;
      const i = Math.floor(t);
      if (i >= frames.length - 1) {
        slider.value = 50;
        slider.dispatchEvent(new Event("input", { bubbles: true }));
        return;
      }
      const f = t - i;
      const ease = f < 0.5 ? 2 * f * f : 1 - (-2 * f + 2) ** 2 / 2;
      slider.value = frames[i] + (frames[i + 1] - frames[i]) * ease;
      slider.dispatchEvent(new Event("input", { bubbles: true }));
      sliderAnimation = requestAnimationFrame(tick);
    };
    sliderAnimation = requestAnimationFrame(tick);
  };

  // Each step: target (selector or null for a centred card), title, body,
  // optional value line, and an optional action that sets up the page first.
  const STEPS = [
    {
      target: null,
      title: "مرحباً بكم في مرصاد",
      body: "منصة لرصد الفيضانات من صور رادار القمر الصناعي NISAR. الرادار يرى من خلال السحب والمطر، ويعمل ليلاً ونهاراً، فيكشف المناطق المغمورة بالمياه حتى في أسوأ الأحوال الجوية.",
      value: "في هذه الجولة نستعرض كل أداة في المنصة وما تقدمه من قيمة.",
    },
    {
      target: ".run-picker",
      title: "اختيار عملية التحليل",
      body: "من هنا نختار المنطقة والحدث الذي نريد تحليله. كل عملية تحتوي على صورتي رادار (قبل الحدث وبعده) ونتائج التحليل الخاصة بها.",
      value: "المنصة مبنية لتستوعب أي منطقة جديدة دون تغيير في الواجهة.",
    },
    {
      target: ".scene-header",
      title: "بطاقة الحدث وحالته",
      body: "يظهر هنا اسم المنطقة والحدث، ومعه شارة توضح حالة البيانات بصراحة: هل هي بيانات حقيقية تم التحقق منها، أم تحليل استكشافي، أم بيانات تجريبية.",
      value: "الشفافية أولاً: لا نعرض نتيجة دون أن نوضح درجة موثوقيتها.",
    },
    {
      target: "#map-frame",
      title: "خريطة الرادار التفاعلية",
      body: "هذه صور الرادار الفعلية للمنطقة. يمكن التكبير والتصغير والتحرك على الخريطة لفحص أي جزء بالتفصيل.",
      value: "في صور الرادار تظهر المياه داكنة لأنها سطح أملس يعكس الإشارة بعيداً عن القمر الصناعي.",
    },
    {
      target: "#slider",
      pad: 6,
      title: "المقارنة بين قبل وبعد",
      body: "اسحب هذا المؤشر يميناً ويساراً للمقارنة المباشرة بين صورة ما قبل الفيضان وصورة ما بعده على نفس المكان.",
      value: "تُظهر بعين المشاهد حجم التغير خلال ثوانٍ، دون الحاجة لخبرة في تحليل الصور.",
      action: demoSlider,
    },
    {
      target: "#scene-labels",
      title: "تواريخ الالتقاط",
      body: "على اليسار تاريخ صورة ما قبل الحدث، وعلى اليمين تاريخ صورة ما بعده، ليعرف المستخدم الفترة الزمنية التي يغطيها التحليل.",
    },
    {
      target: ".radar-key",
      title: "مفتاح قراءة الرادار",
      body: "يوضح شدة الإشارة المرتدة (بوحدة الديسيبل): كلما كان اللون أغمق كانت الإشارة أضعف، وهذا غالباً يدل على وجود مياه.",
    },
    {
      target: "#reset-view",
      pad: 6,
      title: "إعادة ضبط العرض",
      body: "بعد التكبير أو التنقل، يعيد هذا الزر الخريطة إلى كامل منطقة الدراسة بضغطة واحدة.",
    },
    {
      target: ".run-totals",
      title: "ملخص النتائج",
      body: "عدد المناطق المرشحة للتغير، والمساحة الإجمالية بالكيلومتر المربع.",
      value: "رقم واضح يعطي صاحب القرار تصوراً سريعاً لحجم المنطقة المتأثرة.",
    },
    {
      target: "#reveal",
      pad: 6,
      title: "كشف التغيرات",
      body: "بضغطة واحدة تُظهر المنصة المناطق التي تغيرت بين الصورتين، ويحيط بكل منطقة إطار ملون حسب نوع التغير.",
      value: "يحول آلاف البكسلات من بيانات الرادار إلى خريطة واضحة لمواقع الفيضان.",
      action: () => { setToggle("review-only", false); setToggle("smart-doubt", false); setReveal(true); },
    },
    {
      target: "#layer-key",
      title: "تصنيف التغيرات",
      body: "كل لون له معنى: أزرق = فيضان مرجح، برتقالي = فيضان محتمل، رمادي فاتح = تغير من نوع آخر.",
      value: "لا نكتفي بقول «هنا تغير»، بل نصنفه لنفرق بين الفيضان وغيره.",
      action: () => setReveal(true),
    },
    {
      target: ".analysis-controls label:first-of-type",
      pad: 6,
      title: "ميزة الشك الذكي (Smart Doubt)",
      body: "ميزة مميزة في مرصاد: تختبر المنصة كل منطقة على عدة عتبات للكشف، ثم تلون المناطق حسب ثبات النتيجة. الأخضر = نتيجة ثابتة عبر كل العتبات، الأصفر = ثبات متوسط، الوردي المتقطع = نتيجة حساسة تحتاج مراجعة.",
      value: "المنصة تخبرك بصدق أين النتيجة مستقرة وأين قد تتغير، وهذا ما تفتقده كثير من الأنظمة.",
      action: () => { setReveal(true); setToggle("smart-doubt", true); },
    },
    {
      target: ".analysis-controls label:last-child",
      pad: 6,
      title: "عرض ما يحتاج مراجعة فقط",
      body: "عند تفعيله تخفي المنصة المناطق الموثوقة وتُبقي فقط المناطق غير المؤكدة.",
      value: "يوفر وقت المحلل ويوجه جهد المراجعة البشرية إلى حيث تكون الحاجة فعلاً.",
      action: () => { setReveal(true); setToggle("smart-doubt", true); setToggle("review-only", true); },
    },
    {
      target: "#inspect",
      title: "البحث عن منطقة وفحصها",
      body: "اختر أي منطقة من القائمة واضغط «Inspect» لتنتقل الخريطة إليها مباشرة، أو اضغط على أي منطقة في الخريطة.",
      action: () => { setToggle("review-only", false); setToggle("smart-doubt", false); setReveal(true); },
    },
    {
      target: "#map .leaflet-popup",
      pad: 6,
      title: "بطاقة الدليل (Evidence Card)",
      body: "لكل منطقة بطاقة تشرح سبب تصنيفها: قيمة الإشارة قبل وبعد، ومقدار التغير، والمساحة، ودرجة الشك، مع شرح نصي للسبب.",
      value: "النتيجة قابلة للتفسير والتحقق، وليست صندوقاً أسود. كل قرار مدعوم بالأرقام.",
      action: () => { setReveal(true); inspectFirstArea(); },
      wait: 250,
    },
    {
      target: "#method",
      title: "المنهجية والقيود",
      body: "هنا نوثق طريقة التحليل، ونتائج المقارنة مع بيانات مرجعية مستقلة، والقيود المعروفة للمنهج.",
      value: "الأمانة العلمية جزء من المنتج: يعرف المستخدم متى يثق بالنتيجة ومتى يتحقق منها.",
      action: () => { closePopup(); $("method").open = true; },
    },
    {
      target: null,
      title: "مرصاد باختصار",
      body: "رصد سريع للفيضانات في أي طقس • تصنيف واضح للتغيرات • شك ذكي يبين ثبات النتيجة • بطاقة دليل لكل منطقة • شفافية كاملة في المنهجية.",
      value: "من صورة رادار خام إلى قرار مدعوم بالأدلة، في واجهة واحدة بسيطة.",
      action: () => { $("method").open = false; },
    },
  ];

  const ui = {};
  let index = -1;
  let snapshot;
  let target;

  function build() {
    ui.root = document.createElement("div");
    ui.root.className = "tour";
    ui.root.hidden = true;
    ui.root.innerHTML = `
      <div class="tour-spotlight" aria-hidden="true"></div>
      <section class="tour-card" role="dialog" aria-modal="false" aria-labelledby="tour-title" aria-describedby="tour-body" dir="rtl" lang="ar">
        <div class="tour-head">
          <span class="tour-count" id="tour-count"></span>
          <button type="button" class="tour-close" id="tour-close" aria-label="إنهاء الجولة">×</button>
        </div>
        <h2 id="tour-title" tabindex="-1"></h2>
        <p id="tour-body"></p>
        <p class="tour-value" id="tour-value"></p>
        <div class="tour-progress" aria-hidden="true"><span id="tour-bar"></span></div>
        <div class="tour-nav">
          <button type="button" id="tour-prev">السابق</button>
          <button type="button" class="primary" id="tour-next">التالي</button>
        </div>
      </section>`;
    document.body.append(ui.root);
    for (const id of ["count", "title", "body", "value", "bar", "prev", "next", "close"]) ui[id] = $(`tour-${id}`);
    ui.spot = ui.root.querySelector(".tour-spotlight");
    ui.card = ui.root.querySelector(".tour-card");
    ui.prev.addEventListener("click", () => go(index - 1, -1));
    ui.next.addEventListener("click", () => (index === STEPS.length - 1 ? stop() : go(index + 1, 1)));
    ui.close.addEventListener("click", stop);
  }

  const visible = (element) => element && element.getClientRects().length > 0 && !element.closest("[hidden]");

  async function go(next, direction) {
    stopSlider();
    // Skip steps whose element is not on the page (for example before data loads).
    while (next >= 0 && next < STEPS.length) {
      const step = STEPS[next];
      step.action?.();
      if (step.wait) await new Promise((resolve) => setTimeout(resolve, step.wait));
      const element = step.target && q(step.target);
      if (!step.target || visible(element)) break;
      next += direction;
    }
    if (next < 0 || next >= STEPS.length) return direction > 0 ? stop() : undefined;
    index = next;
    const step = STEPS[index];
    target = step.target ? q(step.target) : null;
    ui.count.textContent = `الخطوة ${index + 1} من ${STEPS.length}`;
    ui.title.textContent = step.title;
    ui.body.textContent = step.body;
    ui.value.textContent = step.value ?? "";
    ui.value.hidden = !step.value;
    ui.bar.style.width = `${((index + 1) / STEPS.length) * 100}%`;
    ui.prev.disabled = index === 0;
    ui.next.textContent = index === STEPS.length - 1 ? "إنهاء الجولة" : index === 0 ? "لنبدأ" : "التالي";
    target?.scrollIntoView({ block: "center", inline: "nearest" });
    place();
    ui.title.focus({ preventScroll: true });
  }

  function place() {
    if (index < 0) return;
    const pad = STEPS[index].pad ?? 10;
    const card = ui.card;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    card.classList.toggle("centered", !target);
    ui.spot.classList.toggle("empty", !target);
    if (!target) {
      card.style.left = card.style.top = "";
      return;
    }
    const r = target.getBoundingClientRect();
    const box = {
      left: Math.max(4, r.left - pad), top: Math.max(4, r.top - pad),
      right: Math.min(vw - 4, r.right + pad), bottom: Math.min(vh - 4, r.bottom + pad),
    };
    Object.assign(ui.spot.style, {
      left: `${box.left}px`, top: `${box.top}px`,
      width: `${box.right - box.left}px`, height: `${box.bottom - box.top}px`,
    });

    const gap = 14;
    const cw = card.offsetWidth;
    const ch = card.offsetHeight;
    const clampX = (x) => Math.min(vw - cw - 12, Math.max(12, x));
    const clampY = (y) => Math.min(vh - ch - 12, Math.max(12, y));
    const centerX = (box.left + box.right) / 2 - cw / 2;
    const centerY = (box.top + box.bottom) / 2 - ch / 2;
    let left;
    let top;
    if (vh - box.bottom >= ch + gap) [left, top] = [clampX(centerX), box.bottom + gap];
    else if (box.top >= ch + gap) [left, top] = [clampX(centerX), box.top - gap - ch];
    else if (box.left >= cw + gap) [left, top] = [box.left - gap - cw, clampY(centerY)];
    else if (vw - box.right >= cw + gap) [left, top] = [box.right + gap, clampY(centerY)];
    else [left, top] = [clampX(centerX), vh - ch - 12]; // Large targets: card sits inside, at the bottom.
    card.style.left = `${left}px`;
    card.style.top = `${top}px`;
  }

  function start() {
    if (!ui.root) build();
    snapshot = {
      reveal: $("reveal").getAttribute("aria-pressed") === "true",
      smartDoubt: $("smart-doubt").checked,
      reviewOnly: $("review-only").checked,
      method: $("method").open,
      scroll: window.scrollY,
    };
    ui.root.hidden = false;
    document.body.classList.add("touring");
    $("tour-toggle").setAttribute("aria-pressed", "true");
    $("tour-toggle-label").textContent = "إنهاء الجولة التعريفية";
    go(0, 1);
  }

  function stop() {
    if (index < 0) return;
    stopSlider();
    index = -1;
    target = null;
    ui.root.hidden = true;
    document.body.classList.remove("touring");
    closePopup();
    // Put the page back the way the presenter left it.
    setToggle("review-only", false);
    setToggle("smart-doubt", snapshot.smartDoubt);
    setReveal(snapshot.reveal);
    setToggle("review-only", snapshot.reviewOnly);
    $("method").open = snapshot.method;
    $("slider").value = 50;
    $("slider").dispatchEvent(new Event("input", { bubbles: true }));
    if (!$("reset-view").disabled) $("reset-view").click();
    window.scrollTo({ top: snapshot.scroll });
    $("tour-toggle").setAttribute("aria-pressed", "false");
    $("tour-toggle-label").textContent = "ابدأ الجولة التعريفية";
    $("tour-toggle").focus({ preventScroll: true });
  }

  $("tour-toggle").addEventListener("click", () => (index < 0 ? start() : stop()));
  document.addEventListener("keydown", (event) => {
    if (index < 0) return;
    if (event.key === "Escape") stop();
    // The card is right-to-left, so the left arrow moves forward.
    else if (event.key === "ArrowLeft" && event.target.id !== "slider") ui.next.click();
    else if (event.key === "ArrowRight" && event.target.id !== "slider" && !ui.prev.disabled) ui.prev.click();
  });
  const reposition = () => requestAnimationFrame(place);
  window.addEventListener("resize", reposition);
  window.addEventListener("scroll", reposition, { passive: true });
  new ResizeObserver(reposition).observe(document.body);

  // Open the page with ?tour to start presenting straight away.
  if (new URLSearchParams(location.search).has("tour")) {
    const ready = () => (!$("reveal").disabled ? start() : setTimeout(ready, 200));
    ready();
  }
})();
