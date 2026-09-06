/* الاسم بالعربي — نفس قاعدة السيرفر بالحرف.
 *
 * القاعدة الحقيقية في `backend/app/services/name_utils.py::is_arabic_name`،
 * وهي اللي بترفض فعلاً. الملف ده موجود عشان العضو يعرف دلوقتي مش بعد ما
 * يضغط، والرسالة اللي هيقراها تبقى نفس الرسالة.
 *
 * النمطين تحت منقولين حرفياً من `ARABIC_NAME_PATTERN` و`ARABIC_LETTER_PATTERN`
 * في نفس الملف — وفيه اختبار (`test_the_js_rule_is_the_python_rule`) بيقرا
 * الملف ده ويقارن السطرين. لو اتغيّر واحد من غير التاني الاختبار بيقع، عشان
 * قاعدتين بتفرقوا معناها إن الفورم بيقول «تمام» والسيرفر بيقول «لأ».
 *
 * ليه ملف لوحده مش جوه utils.js: `index.html` مش بيحمّل utils.js عن قصد
 * (تعارض globals مع main.js — مكتوب هناك)، وفورم التسجيل الموجود في المودال
 * بتاعها محتاج نفس القاعدة. الملف ده بيعرّف global واحد بس.
 */
(function () {
  var NAME_RE = /^[\u0621-\u063A\u0641-\u064A\u066E-\u06D3\u0750-\u077F\u08A0-\u08BF\u064B-\u0652\u0640 ]+$/;
  var LETTER_RE = /[\u0621-\u063A\u0641-\u064A\u066E-\u06D3\u0750-\u077F\u08A0-\u08BF]/g;

  /** هل ده اسم مكتوب بالعربي كله؟ `Mohamed محمد` لأ — كل حرف لازم يكون عربي. */
  window.isArabicName = function (value) {
    var s = String(value == null ? '' : value).trim().replace(/\s+/g, ' ');
    if (!s) return false;
    if (!NAME_RE.test(s)) return false;
    return (s.match(LETTER_RE) || []).length >= 2;
  };

  /** فيه حرف مش مسموح بيه؟ — للتحقق الفوري وإنت بتكتب.
   *
   * مش `isArabicName` مقلوبة: دي بتطلب حرفين عربي على الأقل، فأول ما تكتب
   * `م` تبقى False والغلط يظهر في وش العضو وهو لسه بيكتب اسمه صح. السؤال
   * هنا أضيق: هل فيه حرف مايصحش يتكتب أصلاً؟ ده اللي ينفع يترد عليه فوراً.
   *
   * بتقيس بـ `NAME_RE` نفسها حرف حرف — مفيش نمط تاني يتكتب بالإيد هنا، لأن
   * نسختين من نفس القاعدة هما بالظبط اللي الاختبار بتاع التطابق موجود
   * عشانهم. النمط متثبّت بـ ^...+$ فهو بيوافق حرف واحد لو الحرف مسموح.
   */
  window.hasNonArabicChar = function (value) {
    var s = String(value == null ? '' : value);
    for (var i = 0; i < s.length; i++) {
      if (!NAME_RE.test(s[i])) return true;
    }
    return false;
  };

  /** الرسالة الوحيدة — نفس نص `ARABIC_NAME_MESSAGE` في بايثون. */
  window.ARABIC_NAME_MESSAGE = 'برجاء كتابة الاسم باللغة العربية';
})();
