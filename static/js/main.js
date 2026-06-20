/**
 * 智农首页交互已统一在 templates/index.html 内联脚本中维护。
 * 请勿在本页重复绑定上传/预览逻辑，避免与 index 冲突。
 * 若需抽离，请将 index 中 (function(){ ... })(); 迁移至此并只保留一处 script 引用。
 */
(function() {
  'use strict';
  if (typeof console !== 'undefined' && console.info) {
    console.info('[zhinong] main.js 为占位文件，实际上传/预览/批量逻辑见 index.html');
  }
})();