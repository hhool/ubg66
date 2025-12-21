doSearch= function() {
    const val= $("#search-input").val().trim().replace(/ /g, "-");
    if (val!= "") {
        // alert(val);
        window.location= "/search.html?q="+ val;
    }
}

$("#search-input").on('keyup', function (e) {
    if (e.key === 'Enter' || e.keyCode === 13) {        
        doSearch();
    }
});

$( "#search-button" ).on( "click", function() {  
    doSearch();
});

$( document ).ready(function() {
    $("#search-input").focus();
});