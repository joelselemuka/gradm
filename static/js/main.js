$(document).on("click", "#filter_search", function () {
  $("#filter_inputs").slideToggle(150);
});

var selectAllItems = "#select-all";
var checkboxItem = ":checkbox";
$(selectAllItems).click(function () {
  if (this.checked) {
    $(checkboxItem).each(function () {
      this.checked = true;
    });
  } else {
    $(checkboxItem).each(function () {
      this.checked = false;
    });
  }
});
var selectAllItems = "#select-all2";
var checkboxItem = ":checkbox";
$(selectAllItems).click(function () {
  if (this.checked) {
    $(checkboxItem).each(function () {
      this.checked = true;
    });
  } else {
    $(checkboxItem).each(function () {
      this.checked = false;
    });
  }
});
// init();
$(document).on("click", "#toggle_btn", function () {
  if ($("body").hasClass("mini-sidebar")) {
    $("body").removeClass("mini-sidebar");
    $(this).addClass("active");
    $(".subdrop + ul");
    localStorage.setItem("screenModeNightTokenState", "night");
    setTimeout(function () {
      $("body").removeClass("mini-sidebar");
      $(".header-left").addClass("active");
    }, 100);
  } else {
    $("body").addClass("mini-sidebar");
    $(this).removeClass("active");
    $(".subdrop + ul");
    localStorage.removeItem("screenModeNightTokenState", "night");
    setTimeout(function () {
      $("body").addClass("mini-sidebar");
      $(".header-left").removeClass("active");
    }, 100);
  }
  return false;
});
$(document).on("mouseover", function (e) {
  e.stopPropagation();
  if ($("body").hasClass("mini-sidebar") && $("#toggle_btn").is(":visible")) {
    var targ = $(e.target).closest(".sidebar, .header-left").length;
    if (targ) {
      $("body").addClass("expand-menu");
      $(".subdrop + ul").slideDown();
    } else {
      $("body").removeClass("expand-menu");
      $(".subdrop + ul").slideUp();
    }
    return false;
  }
});

// $(function () {
//   oTable = $("#table").DataTable({
//     bFilter: true,
//     sDom: "fBtlpi",
//     ordering: true,
//     language: {
//       search: " ",
//       sLengthMenu: "_MENU_",
//       searchPlaceholder: "Recherche",
//       info: "_START_ - _END_ of _TOTAL_ items",
//       paginate: {
//         next: ' <i class=" fa fa-angle-right"></i>',
//         previous: '<i class="fa fa-angle-left"></i> ',
//       },
//     },
//     buttons: [
//       {
//         extend: "excel",
//         class: "buttons-excel",
//         init: function (api, node, config) {
//           $(node).hide();
//         },
//       },
//       {
//         extend: "pdf",
//         class: "buttons-pdf",
//         init: function (api, node, config) {
//           $(node).hide();
//         },
//       },
//       {
//         extend: "print",
//         class: "buttons-print",
//         init: function (api, node, config) {
//           $(node).hide();
//         },
//       },
//     ],
//     order: [],
//     columnDefs: [
//       {
//         targets: "no-sort",
//         orderable: false,
//       },
//     ],
//   });
// });

// $("#tableSearch").on("keyup", function () {
//   oTable.search($(this).val()).draw();
// });

// $("#tableLen").change(function () {
//   oTable.page.len($(this).val()).draw();
// });
// $("#status").change(function () {
//   oTable.search($(this).val()).draw();
// });
// $("#btn_print").on("click", function () {
//   oTable.button(".buttons-print").trigger();
// });
// $("#btn_pdf").on("click", function () {
//   oTable.button(".buttons-pdf").trigger();
// });
// $("#btn_excel").on("click", function () {
//   oTable.button(".buttons-excel").trigger();
// });

$(function () {
  oTable = $("#table").DataTable({
    bFilter: true,
    sDom: "fBtlpi",
    ordering: true,
    language: {
      search: " ",
      sLengthMenu: "_MENU_",
      searchPlaceholder: "Recherche",
      info: "_START_ - _END_ of _TOTAL_ items",
      paginate: {
        next: ' <i class=" fa fa-angle-right"></i>',
        previous: '<i class="fa fa-angle-left"></i> ',
        first: '<i class="fa fa-step-backward"></i>',
        last: '<i class="fa fa-step-forward"></i>',
      },
    },
    buttons: [
      {
        extend: "excel",
        class: "buttons-excel",
        init: function (api, node, config) {
          $(node).hide();
        },
      },
      {
        extend: "pdf",
        class: "buttons-pdf",
        init: function (api, node, config) {
          $(node).hide();
        },
      },
      {
        extend: "print",
        class: "buttons-print",
        init: function (api, node, config) {
          $(node).hide();
        },
      },
    ],
    order: [],
    columnDefs: [
      {
        targets: "no-sort",
        orderable: false,
      },
    ],
  });
  // ZONNE DE RECHERCHE
  $("#tableSearch").on("keyup", function () {
    oTable.search($(this).val()).draw();
  });
  // CHANGER LES NBRE D'ELEMENTS A AFFICHER
  $("#tableLen").change(function () {
    oTable.page.len($(this).val()).draw();
  });
  // FILTRAGE PAR STATUT
  $("#status").change(function () {
    oTable
      .column(3)
      .search("^" + $(this).val() + "$", true, false)
      .draw();
  });
  $("#btn_print").on("click", function () {
    oTable.button(".buttons-print").trigger();
  });
  $("#btn_pdf").on("click", function () {
    oTable.button(".buttons-pdf").trigger();
  });
  $("#btn_excel").on("click", function () {
    oTable.button(".buttons-excel").trigger();
  });
});
