"""
Add new narrative keys for Part 3 of the i18n/narrative task.

New narrative keys added per locale:
  narratives.germany.ranks:  gefreiter, fhj_oberfeldwebel, general_der_jagdflieger
  narratives.britain.ranks:  corporal, air_marshal, air_chief_marshal
  narratives.soviet.ranks:   efreitor, mladshiy_serzhant, general_polkovnik
  narratives.usa.ranks:      staff_sergeant, technical_sergeant, lieutenant_general
  narratives.britain.awards: third_bar_to_the_distinguished_service_order, france_and_germany_star
  narratives.usa.awards:     air_medal_plus_four_oak_leaf_clusters,
                              air_medal_plus_one_silver_leaf_cluster,
                              european_african_middle_eastern_campaign_medal
  narratives.soviet.awards:  aircraft_kill_bonus_1000_rubles,
                              fighter_kill_bonus_1000_rubles,
                              transport_plane_kill_bonus_1500_rubles,
                              bomber_kill_bonus_1500_rubles, bomber_kill_bonus_2000_rubles,
                              small_ship_kill_bonus_1000_rubles,
                              transport_ship_kill_bonus_3000_rubles,
                              destroyer_or_submarine_kill_bonus_10000_rubles,
                              medal_for_the_defense_of_moscow,
                              medal_for_the_defense_of_stalingrad,
                              medal_for_the_defense_of_the_caucasus
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
LOCALES = ROOT / "locales"


def deep_set(obj: dict, keys: list, value):
    for k in keys[:-1]:
        obj = obj.setdefault(k, {})
    if keys[-1] not in obj:
        obj[keys[-1]] = value
        return True
    return False


def load(lang):
    with open(LOCALES / f"{lang}.json", encoding="utf-8") as f:
        return json.load(f)


def save(lang, data):
    with open(LOCALES / f"{lang}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


# ---------------------------------------------------------------------------
# English narratives — master
# ---------------------------------------------------------------------------
EN = {
    # Germany ranks
    ("narratives", "germany", "ranks", "gefreiter"):
        "Your first stripe in a war that doesn't slow down for paperwork. "
        "You've earned enough trust for a chevron; now earn enough to keep it.",

    ("narratives", "germany", "ranks", "fhj_oberfeldwebel"):
        "Officer candidate with NCO rank—still waiting on the commission while flying like "
        "it's already yours. The paperwork will catch up. Keep performing.",

    ("narratives", "germany", "ranks", "general_der_jagdflieger"):
        "You direct the entire fighter arm. Operational priorities, unit dispositions, "
        "doctrine under fire—these are your instruments now. The sky belongs to the men "
        "you send into it.",

    # Britain ranks
    ("narratives", "britain", "ranks", "corporal"):
        "Two chevrons and a small section depending on you. The RAF runs on men "
        "who keep it together at this level. Be that man.",

    ("narratives", "britain", "ranks", "air_marshal"):
        "You think in air campaigns, not sorties. Resources, strategy, and politics at "
        "the highest level. You may still fly—but the war moves through your decisions first.",

    ("narratives", "britain", "ranks", "air_chief_marshal"):
        "The peak of operational rank. What you decide shapes the shape of the air war. "
        "Every RAF wing in the theatre answers, ultimately, to a chain that ends here.",

    # Soviet ranks
    ("narratives", "soviet", "ranks", "efreitor"):
        "One step above the bottom. The stripe is small; the expectations just got larger. "
        "You show up, you hold the line, you don't cost anyone extra effort. That's the job.",

    ("narratives", "soviet", "ranks", "mladshiy_serzhant"):
        "Junior sergeant. The title is small but the role is real. "
        "Someone is now watching how you handle pressure. Don't let them down.",

    ("narratives", "soviet", "ranks", "general_polkovnik"):
        "Command at the scale of armies. You coordinate fronts, allocate air armies, "
        "and answer to the Stavka. The individual aircraft are abstractions; "
        "you move the whole instrument of air power.",

    # USA ranks
    ("narratives", "usa", "ranks", "staff_sergeant"):
        "Three up, two down. You are the institutional memory of your unit and the "
        "backbone of its discipline. Officers set direction; you make it work.",

    ("narratives", "usa", "ranks", "technical_sergeant"):
        "Technical Sergeant. You keep the machines running and the crews honest. "
        "What you know about this aircraft is what keeps it flying and the men in it alive.",

    ("narratives", "usa", "ranks", "lieutenant_general"):
        "Three stars. You run air campaigns across theaters and shape the strategy "
        "that aircrew execute at altitude. The men at the sharp end are distant—"
        "but every decision you make echoes in the sky over them.",

    # Britain awards
    ("narratives", "britain", "awards", "third_bar_to_the_distinguished_service_order"):
        "A third bar to the DSO. Three separate recognitions, each requiring a standard "
        "most officers never meet once. The ribbon has grown; so has what's expected of you.",

    ("narratives", "britain", "awards", "france_and_germany_star"):
        "The final campaign. From Normandy to the Reich—you were flying when the war in "
        "Western Europe reached its conclusion. The star marks a road that ended in German airspace.",

    # USA awards
    ("narratives", "usa", "awards", "air_medal_plus_four_oak_leaf_clusters"):
        "Five awards for aerial achievement under combat conditions. "
        "The clusters are the war's arithmetic: each one is more sorties, more exposure, "
        "more of the same sky that doesn't get any safer.",

    ("narratives", "usa", "awards", "air_medal_plus_one_silver_leaf_cluster"):
        "A silver oak leaf cluster in lieu of five additional awards. "
        "The ribbon can't keep up with the missions. The flying kept going anyway.",

    ("narratives", "usa", "awards", "european_african_middle_eastern_campaign_medal"):
        "Across the theaters that turned the war. North Africa, the Mediterranean, "
        "the approaches to Europe—you were there while the strategic balance shifted. "
        "The medal marks the geography of a victory that wasn't guaranteed.",

    # Soviet awards
    ("narratives", "soviet", "awards", "aircraft_kill_bonus_1000_rubles"):
        "The state pays for kills. One thousand rubles confirms that you fired, "
        "connected, and removed an aircraft from the enemy's count.",

    ("narratives", "soviet", "awards", "fighter_kill_bonus_1000_rubles"):
        "Fighter downed. The threat is gone and the payment follows. "
        "A thousand rubles for a kill that may have saved a wingman.",

    ("narratives", "soviet", "awards", "transport_plane_kill_bonus_1500_rubles"):
        "A transport removed from the supply equation. Fifteen hundred rubles "
        "for cutting a logistics thread the enemy was counting on.",

    ("narratives", "soviet", "awards", "bomber_kill_bonus_1500_rubles"):
        "Bomber down before it reached the target. Fifteen hundred rubles "
        "for the mission it never completed.",

    ("narratives", "soviet", "awards", "bomber_kill_bonus_2000_rubles"):
        "Another bomber removed from the enemy's order of battle. "
        "The bonus reflects the threat level. Two thousand rubles for keeping "
        "what lies below intact.",

    ("narratives", "soviet", "awards", "small_ship_kill_bonus_1000_rubles"):
        "A small vessel put out of action. The bonus is modest; "
        "the result—one fewer enemy asset on the water—is not.",

    ("narratives", "soviet", "awards", "transport_ship_kill_bonus_3000_rubles"):
        "A transport ship is not just a target—it is a supply chain. "
        "Three thousand rubles for stopping what it was carrying from arriving.",

    ("narratives", "soviet", "awards", "destroyer_or_submarine_kill_bonus_10000_rubles"):
        "A warship of substance—destroyer or submarine. "
        "Ten thousand rubles because the threat to friendly forces and supply "
        "lines was correspondingly serious. It won't be on the water again.",

    ("narratives", "soviet", "awards", "medal_for_the_defense_of_moscow"):
        "Moscow itself was in the balance. You flew above a city that couldn't afford "
        "to fall, and it didn't. This medal records the battle that kept the war alive.",

    ("narratives", "soviet", "awards", "medal_for_the_defense_of_stalingrad"):
        "Stalingrad—the battle that broke the Wehrmacht's strategic momentum. "
        "You were in the air above the city while it absorbed the worst the enemy "
        "could send. The medal marks a moment that changed the entire war.",

    ("narratives", "soviet", "awards", "medal_for_the_defense_of_the_caucasus"):
        "The Caucasus campaign: oil, mountain passes, and the edge of a disaster "
        "that was turned back. You flew in the battles that kept the fuel "
        "and the southern flank out of enemy hands.",
}

# ---------------------------------------------------------------------------
# German translations
# ---------------------------------------------------------------------------
DE = {
    ("narratives", "germany", "ranks", "gefreiter"):
        "Dein erster Streifen in einem Krieg, der nicht auf Papierarbeit wartet. "
        "Du hast genug Vertrauen f\u00fcr ein Chevron erworben\u2014jetzt halte es.",

    ("narratives", "germany", "ranks", "fhj_oberfeldwebel"):
        "Offiziersanw\u00e4rter mit Unteroffiziersdienstgrad\u2014wartest auf die Bestellung "
        "und fliegst, als ob sie schon erteilt w\u00e4re. Der Papierkram holt dich ein. Bleib dran.",

    ("narratives", "germany", "ranks", "general_der_jagdflieger"):
        "Du f\u00fchrst den gesamten Jagdfliegerverband. Einsatzpriori\u00e4ten, Verbandsstellung, "
        "Doktrin unter Feuer\u2014das sind jetzt deine Werkzeuge. Der Himmel geh\u00f6rt "
        "den M\u00e4nnern, die du hinaufschickst.",

    ("narratives", "britain", "ranks", "corporal"):
        "Zwei Winkel und ein kleiner Trupp, der auf dich z\u00e4hlt. Die RAF steht und "
        "f\u00e4llt mit M\u00e4nnern, die auf dieser Ebene zusammenhalten. Sei dieser Mann.",

    ("narratives", "britain", "ranks", "air_marshal"):
        "Du denkst in Luftkampagnen, nicht in Eins\u00e4tzen. Ressourcen, Strategie "
        "und Entscheidungen auf h\u00f6chster Ebene. Du fliegst vielleicht noch\u2014"
        "aber der Krieg l\u00e4uft zuerst durch deine Befehle.",

    ("narratives", "britain", "ranks", "air_chief_marshal"):
        "Der Gipfel des operativen Dienstgrades. Deine Entscheidungen pr\u00e4gen "
        "den Luftkrieg. Jeder RAF-Verband im Theater antwortet letztlich auf "
        "eine Kette, die hier endet.",

    ("narratives", "soviet", "ranks", "efreitor"):
        "Einen Schritt \u00fcber dem Boden. Der Streifen ist klein; "
        "die Erwartungen sind gerade gr\u00f6\u00dfer geworden. "
        "Erschein, halte die Linie, koste niemanden zus\u00e4tzlich Aufwand. Das ist der Job.",

    ("narratives", "soviet", "ranks", "mladshiy_serzhant"):
        "Junger Unteroffizier. Der Titel ist bescheiden, aber die Rolle ist real. "
        "Jemand beobachtet, wie du mit Druck umgehst. Entt\u00e4usch ihn nicht.",

    ("narratives", "soviet", "ranks", "general_polkovnik"):
        "Befehlsgewalt auf Armeeebene. Du koordinierst Fronten, verteilst Luftarmeen "
        "und berichtest an das Stawka. Die einzelnen Flugzeuge sind Abstraktion; "
        "du bewegst das gesamte Instrument der Luftmacht.",

    ("narratives", "usa", "ranks", "staff_sergeant"):
        "Drei oben, zwei unten. Du bist das institutionelle Ged\u00e4chtnis deiner Einheit "
        "und der R\u00fcckgrat ihrer Disziplin. Offiziere geben die Richtung vor; "
        "du machst es m\u00f6glich.",

    ("narratives", "usa", "ranks", "technical_sergeant"):
        "Technical Sergeant. Du h\u00e4ltst die Maschinen am Laufen und die Besatzungen "
        "bei der Sache. Was du \u00fcber dieses Flugzeug wei\u00dft, h\u00e4lt es in der Luft "
        "und die M\u00e4nner am Leben.",

    ("narratives", "usa", "ranks", "lieutenant_general"):
        "Drei Sterne. Du f\u00fchrst Luftkampagnen \u00fcber ganze Kriegsschaupltze "
        "und pr\u00e4gst die Strategie, die Besatzungen in der H\u00f6he ausf\u00fchren. "
        "Die M\u00e4nner an der Front sind weit weg\u2014aber jede Entscheidung "
        "hallt im Himmel \u00fcber ihnen wider.",

    ("narratives", "britain", "awards", "third_bar_to_the_distinguished_service_order"):
        "Ein dritter Balken zum DSO. Dreimal haben sie einen Standard angelegt, "
        "den die meisten Offiziere nie einmal erreichen. Das Band ist l\u00e4nger; "
        "die Erwartungen auch.",

    ("narratives", "britain", "awards", "france_and_germany_star"):
        "Die letzte Kampagne. Von der Normandie bis zum Reich\u2014du hast geflogen, "
        "als der Krieg in Westeuropa zu Ende ging. Der Stern markiert einen Weg, "
        "der im deutschen Luftraum endete.",

    ("narratives", "usa", "awards", "air_medal_plus_four_oak_leaf_clusters"):
        "F\u00fcnf Auszeichnungen f\u00fcr Leistungen unter Feindeinwirkung. "
        "Die Eichenblatt-Cluster sind die Arithmetik des Krieges: mehr Eins\u00e4tze, "
        "mehr Risiko, derselbe Himmel, der nicht sicherer wird.",

    ("narratives", "usa", "awards", "air_medal_plus_one_silver_leaf_cluster"):
        "Ein silbernes Eichenblatt als Ersatz f\u00fcr f\u00fcnf weitere Auszeichnungen. "
        "Das Band kann mit den Missionen nicht mithalten. Die Fl\u00fcge gingen trotzdem weiter.",

    ("narratives", "usa", "awards", "european_african_middle_eastern_campaign_medal"):
        "\u00dcber die Kriegsschaupltze, die den Krieg wendeten. Nordafrika, "
        "das Mittelmeer, der Weg nach Europa\u2014du warst dabei, "
        "w\u00e4hrend das strategische Gleichgewicht kippte.",

    ("narratives", "soviet", "awards", "aircraft_kill_bonus_1000_rubles"):
        "Der Staat zahlt f\u00fcr Absch\u00fcsse. Tausend Rubel best\u00e4tigen, "
        "dass du gezielt, getroffen und ein Flugzeug aus der Feindrechnung gestrichen hast.",

    ("narratives", "soviet", "awards", "fighter_kill_bonus_1000_rubles"):
        "J\u00e4ger abgeschossen. Die Bedrohung ist beseitigt, die Zahlung folgt. "
        "Tausend Rubel f\u00fcr einen Abschuss, der vielleicht einen Kameraden gerettet hat.",

    ("narratives", "soviet", "awards", "transport_plane_kill_bonus_1500_rubles"):
        "Ein Transportflugzeug aus der Nachschubkette herausgerissen. "
        "Fif\u00fcnfzehnhundert Rubel f\u00fcr das Durchschneiden eines Fadens, "
        "auf den der Feind z\u00e4hlte.",

    ("narratives", "soviet", "awards", "bomber_kill_bonus_1500_rubles"):
        "Bomber vor dem Ziel abgefangen. F\u00fcnfzehnhundert Rubel "
        "f\u00fcr die Mission, die er nie abgeschlossen hat.",

    ("narratives", "soviet", "awards", "bomber_kill_bonus_2000_rubles"):
        "Noch ein Bomber aus dem Kampfauftrag des Feindes herausgel\u00f6st. "
        "Die Pr\u00e4mie spiegelt die Bedrohungsstufe wider. "
        "Zweitausend Rubel, damit bleibt, was unten liegt, heil.",

    ("narratives", "soviet", "awards", "small_ship_kill_bonus_1000_rubles"):
        "Ein kleines Fahrzeug au\u00dfer Gefecht gesetzt. Die Pr\u00e4mie ist bescheiden; "
        "das Ergebnis\u2014ein feindliches Mittel weniger auf dem Wasser\u2014ist es nicht.",

    ("narratives", "soviet", "awards", "transport_ship_kill_bonus_3000_rubles"):
        "Ein Transportschiff ist nicht nur ein Ziel\u2014es ist eine Versorgungslinie. "
        "Dreitausend Rubel daf\u00fcr, dass das, was es transportierte, nicht ankam.",

    ("narratives", "soviet", "awards", "destroyer_or_submarine_kill_bonus_10000_rubles"):
        "Ein Kriegsschiff von Bedeutung\u2014Zerst\u00f6rer oder U-Boot. "
        "Zehntausend Rubel, weil die Bedrohung f\u00fcr eigene Kr\u00e4fte "
        "und Versorgungsrouten entsprechend ernst war. Es wird nicht wieder auftauchen.",

    ("narratives", "soviet", "awards", "medal_for_the_defense_of_moscow"):
        "Moskau selbst stand auf dem Spiel. Du hast \u00fcber einer Stadt geflogen, "
        "die nicht fallen durfte\u2014und sie fiel nicht. "
        "Diese Medaille dokumentiert die Schlacht, die den Krieg am Leben hielt.",

    ("narratives", "soviet", "awards", "medal_for_the_defense_of_stalingrad"):
        "Stalingrad\u2014die Schlacht, die den strategischen Schwung der Wehrmacht brach. "
        "Du warst in der Luft \u00fcber der Stadt, w\u00e4hrend sie das Schlimmste auffing. "
        "Die Medaille markiert einen Moment, der den gesamten Krieg ver\u00e4nderte.",

    ("narratives", "soviet", "awards", "medal_for_the_defense_of_the_caucasus"):
        "Die Kaukasuskampagne: \u00d6l, Gebirgspass und der Rand einer Katastrophe, "
        "die zur\u00fcckgewendet wurde. Du hast in den K\u00e4mpfen geflogen, "
        "die Treibstoff und S\u00fcdflanke vor dem Feind bewahrten.",
}

# ---------------------------------------------------------------------------
# French translations
# ---------------------------------------------------------------------------
FR = {
    ("narratives", "germany", "ranks", "gefreiter"):
        "Votre premi\u00e8re chevron dans une guerre qui n\u2019attend pas les formalit\u00e9s. "
        "Vous avez m\u00e9rit\u00e9 suffisamment de confiance pour ce galon\u2014maintenant, gardez-le.",

    ("narratives", "germany", "ranks", "fhj_oberfeldwebel"):
        "Candidat officier avec un grade de sous-officier\u2014vous attendez votre brevet "
        "tout en volant comme s\u2019il \u00e9tait d\u00e9j\u00e0 l\u00e0. La paperasse vous rattrapera. Continuez.",

    ("narratives", "germany", "ranks", "general_der_jagdflieger"):
        "Vous dirigez l\u2019ensemble de l\u2019arm\u00e9e de chasse. Priorit\u00e9s op\u00e9rationnelles, "
        "dispositifs d\u2019unit\u00e9s, doctrine sous le feu\u2014ce sont vos instruments d\u00e9sormais. "
        "Le ciel appartient aux hommes que vous y envoyez.",

    ("narratives", "britain", "ranks", "corporal"):
        "Deux chevrons et une petite section qui compte sur vous. La RAF fonctionne "
        "gr\u00e2ce aux hommes qui tiennent \u00e0 ce niveau. Soyez cet homme.",

    ("narratives", "britain", "ranks", "air_marshal"):
        "Vous pensez en campagnes a\u00e9riennes, pas en sorties. Ressources, strat\u00e9gie "
        "et politique au plus haut niveau. Vous volez peut-\u00eatre encore\u2014"
        "mais la guerre passe d\u2019abord par vos d\u00e9cisions.",

    ("narratives", "britain", "ranks", "air_chief_marshal"):
        "Le sommet du grade op\u00e9rationnel. Vos d\u00e9cisions fa\u00e7onnent la guerre a\u00e9rienne. "
        "Chaque escadre de la RAF dans le th\u00e9\u00e2tre r\u00e9pond, en d\u00e9finitive, "
        "\u00e0 une cha\u00eene qui s\u2019arr\u00eate ici.",

    ("narratives", "soviet", "ranks", "efreitor"):
        "Un cran au-dessus du bas de l\u2019\u00e9chelle. Le galon est modeste\u2014"
        "les attentes viennent de grandir. Soyez pr\u00e9sent, tenez la ligne, "
        "ne co\u00fbtez rien \u00e0 personne. C\u2019est le travail.",

    ("narratives", "soviet", "ranks", "mladshiy_serzhant"):
        "Sergent junior. Le titre est petit mais le r\u00f4le est r\u00e9el. "
        "Quelqu\u2019un observe maintenant comment vous g\u00e9rez la pression. Ne le d\u00e9cevez pas.",

    ("narratives", "soviet", "ranks", "general_polkovnik"):
        "Commandement \u00e0 l\u2019\u00e9chelle des arm\u00e9es. Vous coordonnez les fronts, "
        "r\u00e9partissez les arm\u00e9es de l\u2019air, r\u00e9pondez au Stavka. "
        "Les avions individuels sont des abstractions\u2014vous manœuvrez l\u2019instrument "
        "entier de la puissance a\u00e9rienne.",

    ("narratives", "usa", "ranks", "staff_sergeant"):
        "Trois galons en haut, deux en bas. Vous \u00eates la m\u00e9moire institutionnelle "
        "de votre unit\u00e9 et l\u2019\u00e9pine dorsale de sa discipline. "
        "Les officiers fixent la direction\u2014vous la rendez possible.",

    ("narratives", "usa", "ranks", "technical_sergeant"):
        "Sergent technique. Vous maintenez les machines en \u00e9tat et les \u00e9quipages alert\u00e9s. "
        "Ce que vous savez sur cet avion, c\u2019est ce qui le garde en vol et les hommes en vie.",

    ("narratives", "usa", "ranks", "lieutenant_general"):
        "Trois \u00e9toiles. Vous conduisez des campagnes a\u00e9riennes \u00e0 travers les th\u00e9\u00e2tres "
        "et fa\u00e7onnez la strat\u00e9gie que les \u00e9quipages ex\u00e9cutent en altitude. "
        "Les hommes en premi\u00e8re ligne sont loin\u2014mais chaque d\u00e9cision "
        "r\u00e9sonne dans le ciel au-dessus d\u2019eux.",

    ("narratives", "britain", "awards", "third_bar_to_the_distinguished_service_order"):
        "Un troisi\u00e8me barrette au DSO. Trois reconnaissances distinctes, "
        "chacune exigeant un standard que la plupart des officiers n\u2019atteignent jamais. "
        "Le ruban s\u2019est allong\u00e9\u2014tout comme ce qu\u2019on attend de vous.",

    ("narratives", "britain", "awards", "france_and_germany_star"):
        "La campagne finale. De la Normandie jusqu\u2019au Reich\u2014vous voliez "
        "quand la guerre en Europe occidentale touchait \u00e0 sa conclusion. "
        "L\u2019\u00e9toile marque une route qui s\u2019est termin\u00e9e dans l\u2019espace a\u00e9rien allemand.",

    ("narratives", "usa", "awards", "air_medal_plus_four_oak_leaf_clusters"):
        "Cinq reconnaissances pour des performances a\u00e9riennes en conditions de combat. "
        "Les agrafes de feuilles de ch\u00eane sont l\u2019arithm\u00e9tique de la guerre\u2014"
        "plus de sorties, plus d\u2019exposition, le m\u00eame ciel qui n\u2019est pas plus s\u00fbr.",

    ("narratives", "usa", "awards", "air_medal_plus_one_silver_leaf_cluster"):
        "Une agrafe en argent en lieu de cinq r\u00e9compenses suppl\u00e9mentaires. "
        "Le ruban ne peut pas suivre le rythme des missions. Les vols ont continu\u00e9 quand m\u00eame.",

    ("narratives", "usa", "awards", "european_african_middle_eastern_campaign_medal"):
        "Sur les th\u00e9\u00e2tres qui ont fait basculer la guerre. Afrique du Nord, "
        "M\u00e9diterran\u00e9e, approches de l\u2019Europe\u2014vous \u00e9tiez l\u00e0 "
        "pendant que l\u2019\u00e9quilibre strat\u00e9gique changeait.",

    ("narratives", "soviet", "awards", "aircraft_kill_bonus_1000_rubles"):
        "L\u2019\u00c9tat paie pour les victoires. Mille roubles confirment que vous avez "
        "vis\u00e9, touch\u00e9, et retir\u00e9 un avion du compte ennemi.",

    ("narratives", "soviet", "awards", "fighter_kill_bonus_1000_rubles"):
        "Chasseur abattu. La menace est \u00e9limin\u00e9e\u2014le paiement suit. "
        "Mille roubles pour un kill qui a peut-\u00eatre sauv\u00e9 un ail\u00e9.",

    ("narratives", "soviet", "awards", "transport_plane_kill_bonus_1500_rubles"):
        "Un avion de transport retir\u00e9 de l\u2019\u00e9quation logistique. "
        "Mille cinq cents roubles pour avoir coup\u00e9 un fil sur lequel l\u2019ennemi comptait.",

    ("narratives", "soviet", "awards", "bomber_kill_bonus_1500_rubles"):
        "Bombardier intercept\u00e9 avant sa cible. Mille cinq cents roubles "
        "pour la mission qu\u2019il n\u2019a jamais achev\u00e9e.",

    ("narratives", "soviet", "awards", "bomber_kill_bonus_2000_rubles"):
        "Un autre bombardier retir\u00e9 de l\u2019ordre de bataille ennemi. "
        "La prime refl\u00e8te le niveau de menace. Deux mille roubles pour "
        "prot\u00e9ger ce qui se trouve en dessous.",

    ("narratives", "soviet", "awards", "small_ship_kill_bonus_1000_rubles"):
        "Un petit b\u00e2timent mis hors de combat. La prime est modeste\u2014"
        "le r\u00e9sultat, un actif ennemi de moins sur l\u2019eau, ne l\u2019est pas.",

    ("narratives", "soviet", "awards", "transport_ship_kill_bonus_3000_rubles"):
        "Un navire de transport n\u2019est pas qu\u2019une cible\u2014c\u2019est une cha\u00eene logistique. "
        "Trois mille roubles pour ce qu\u2019il transportait et qui n\u2019est jamais arriv\u00e9.",

    ("narratives", "soviet", "awards", "destroyer_or_submarine_kill_bonus_10000_rubles"):
        "Un navire de guerre de cons\u00e9quence\u2014destroyer ou sous-marin. "
        "Dix mille roubles parce que la menace \u00e9tait proportionnellement s\u00e9rieuse. "
        "Il ne reviendra pas.",

    ("narratives", "soviet", "awards", "medal_for_the_defense_of_moscow"):
        "Moscou elle-m\u00eame \u00e9tait en jeu. Vous avez vol\u00e9 au-dessus d\u2019une ville "
        "qui ne pouvait pas tomber\u2014et elle n\u2019est pas tomb\u00e9e. "
        "Cette m\u00e9daille enregistre la bataille qui a maintenu la guerre en vie.",

    ("narratives", "soviet", "awards", "medal_for_the_defense_of_stalingrad"):
        "Stalingrad\u2014la bataille qui a bris\u00e9 l\u2019\u00e9lan strat\u00e9gique de la Wehrmacht. "
        "Vous \u00e9tiez dans les airs au-dessus de la ville pendant qu\u2019elle absorbait "
        "le pire de l\u2019ennemi. La m\u00e9daille marque un moment qui a chang\u00e9 la guerre.",

    ("narratives", "soviet", "awards", "medal_for_the_defense_of_the_caucasus"):
        "La campagne du Caucase\u2014p\u00e9trole, cols de montagne, "
        "et le bord d\u2019une catastrophe qui a \u00e9t\u00e9 repouss\u00e9e. "
        "Vous avez vol\u00e9 dans les batailles qui ont prot\u00e9g\u00e9 le carburant "
        "et le flanc sud de l\u2019ennemi.",
}

# ---------------------------------------------------------------------------
# Spanish translations
# ---------------------------------------------------------------------------
ES = {
    ("narratives", "germany", "ranks", "gefreiter"):
        "Tu primer gal\u00f3n en una guerra que no espera el papeleo. "
        "Te has ganado la confianza suficiente para ese chevr\u00f3n\u2014ahora cons\u00e9rvalo.",

    ("narratives", "germany", "ranks", "fhj_oberfeldwebel"):
        "Candidato a oficial con rango de suboficial\u2014a la espera del nombramiento "
        "mientras vuel\u00f3 como si ya lo tuvieras. Los tr\u00e1mites te alcanzar\u00e1n. Sigue rindiendo.",

    ("narratives", "germany", "ranks", "general_der_jagdflieger"):
        "Diriges todo el arma de caza. Prioridades operativas, disposiciones de unidad, "
        "doctrina bajo el fuego\u2014estos son tus instrumentos ahora. "
        "El cielo pertenece a los hombres que env\u00edas a \u00e9l.",

    ("narratives", "britain", "ranks", "corporal"):
        "Dos galones y una peque\u00f1a secci\u00f3n que depende de ti. "
        "La RAF funciona gracias a hombres que aguantan en este nivel. S\u00e9 ese hombre.",

    ("narratives", "britain", "ranks", "air_marshal"):
        "Piensas en campa\u00f1as a\u00e9reas, no en salidas. Recursos, estrategia "
        "y pol\u00edtica al m\u00e1s alto nivel. Quiz\u00e1s a\u00fan vuelas\u2014"
        "pero la guerra pasa primero por tus decisiones.",

    ("narratives", "britain", "ranks", "air_chief_marshal"):
        "La c\u00faspide del rango operativo. Lo que decides moldea la guerra a\u00e9rea. "
        "Cada ala de la RAF en el teatro responde, en \u00faltima instancia, "
        "a una cadena que termina aqu\u00ed.",

    ("narratives", "soviet", "ranks", "efreitor"):
        "Un peld\u00e1\u00f1o por encima del fondo. El gal\u00f3n es peque\u00f1o; "
        "las expectativas acaban de crecer. Preséntate, mantén la l\u00ednea, "
        "no le cuestes esfuerzo extra a nadie. Eso es el trabajo.",

    ("narratives", "soviet", "ranks", "mladshiy_serzhant"):
        "Sargento junior. El t\u00edtulo es modesto pero el papel es real. "
        "Alguien est\u00e1 observando ahora c\u00f3mo manejas la presi\u00f3n. No lo decepciones.",

    ("narratives", "soviet", "ranks", "general_polkovnik"):
        "Mando a escala de ej\u00e9rcito. Coordinas frentes, asignas ej\u00e9rcitos a\u00e9reos "
        "y respondes al Stavka. Los aviones individuales son abstracciones; "
        "t\u00fa mueves el instrumento completo del poder a\u00e9reo.",

    ("narratives", "usa", "ranks", "staff_sergeant"):
        "Tres arriba, dos abajo. Eres la memoria institucional de tu unidad "
        "y la columna vertebral de su disciplina. Los oficiales fijan el rumbo; "
        "t\u00fa lo haces posible.",

    ("narratives", "usa", "ranks", "technical_sergeant"):
        "Sargento t\u00e9cnico. Mantienes las m\u00e1quinas en funcionamiento y las tripulaciones "
        "al tanto. Lo que sabes sobre este avi\u00f3n es lo que lo mantiene volando "
        "y a los hombres con vida.",

    ("narratives", "usa", "ranks", "lieutenant_general"):
        "Tres estrellas. Conduces campa\u00f1as a\u00e9reas a trav\u00e9s de teatros "
        "y moldeas la estrategia que las tripulaciones ejecutan en altura. "
        "Los hombres en primera l\u00ednea est\u00e1n lejos\u2014pero cada "
        "decisi\u00f3n resuena en el cielo sobre ellos.",

    ("narratives", "britain", "awards", "third_bar_to_the_distinguished_service_order"):
        "Un tercer pasador al DSO. Tres reconocimientos separados, cada uno exigiendo "
        "un est\u00e1ndar que la mayor\u00eda de los oficiales nunca alcanzan. "
        "La cinta ha crecido\u2014igual que lo que se espera de ti.",

    ("narratives", "britain", "awards", "france_and_germany_star"):
        "La campa\u00f1a final. Desde Normand\u00eda hasta el Reich\u2014"
        "estabas volando cuando la guerra en Europa occidental lleg\u00f3 a su conclusi\u00f3n. "
        "La estrella marca un camino que termin\u00f3 en espacio a\u00e9reo alem\u00e1n.",

    ("narratives", "usa", "awards", "air_medal_plus_four_oak_leaf_clusters"):
        "Cinco reconocimientos por actuaci\u00f3n en condiciones de combate. "
        "Los racimos de hojas de roble son la aritm\u00e9tica de la guerra: "
        "m\u00e1s salidas, m\u00e1s riesgo, el mismo cielo que no se vuelve m\u00e1s seguro.",

    ("narratives", "usa", "awards", "air_medal_plus_one_silver_leaf_cluster"):
        "Un racimo plateado en lugar de cinco condecoraciones adicionales. "
        "La cinta no puede seguir el ritmo de las misiones. Los vuelos continuaron de todos modos.",

    ("narratives", "usa", "awards", "european_african_middle_eastern_campaign_medal"):
        "A trav\u00e9s de los teatros que giraron la guerra. \u00c1frica del Norte, "
        "el Mediterr\u00e1neo, los accesos a Europa\u2014estabas all\u00ed "
        "mientras el equilibrio estrat\u00e9gico se inclinaba.",

    ("narratives", "soviet", "awards", "aircraft_kill_bonus_1000_rubles"):
        "El Estado paga por las victorias. Mil rublos confirman que apuntaste, "
        "conectaste y retiraste un avi\u00f3n del c\u00f3mputo enemigo.",

    ("narratives", "soviet", "awards", "fighter_kill_bonus_1000_rubles"):
        "Caza derribado. La amenaza ha sido eliminada\u2014el pago sigue. "
        "Mil rublos por un derribo que pudo haber salvado a un compa\u00f1ero.",

    ("narratives", "soviet", "awards", "transport_plane_kill_bonus_1500_rubles"):
        "Un transporte retirado de la ecuaci\u00f3n log\u00edstica. "
        "Mil quinientos rublos por cortar un hilo del que depend\u00eda el enemigo.",

    ("narratives", "soviet", "awards", "bomber_kill_bonus_1500_rubles"):
        "Bombardero interceptado antes de su objetivo. Mil quinientos rublos "
        "por la misi\u00f3n que nunca complet\u00f3.",

    ("narratives", "soviet", "awards", "bomber_kill_bonus_2000_rubles"):
        "Otro bombardero retirado del orden de batalla enemigo. "
        "La bonificaci\u00f3n refleja el nivel de amenaza. Dos mil rublos "
        "por proteger lo que hay abajo.",

    ("narratives", "soviet", "awards", "small_ship_kill_bonus_1000_rubles"):
        "Un peque\u00f1o buque puesto fuera de combate. La bonificaci\u00f3n es modesta; "
        "el resultado\u2014un activo enemigo menos en el agua\u2014no lo es.",

    ("narratives", "soviet", "awards", "transport_ship_kill_bonus_3000_rubles"):
        "Un buque de transporte no es solo un objetivo\u2014es una cadena de suministro. "
        "Tres mil rublos porque lo que transportaba no lleg\u00f3.",

    ("narratives", "soviet", "awards", "destroyer_or_submarine_kill_bonus_10000_rubles"):
        "Un buque de guerra de importancia\u2014destructor o submarino. "
        "Diez mil rublos porque la amenaza para las fuerzas propias era correspondientemente grave. "
        "No volver\u00e1 al agua.",

    ("narratives", "soviet", "awards", "medal_for_the_defense_of_moscow"):
        "Mosc\u00fa misma estaba en juego. Volaste sobre una ciudad que no pod\u00eda caer, "
        "y no cay\u00f3. Esta medalla registra la batalla que mantuvo viva la guerra.",

    ("narratives", "soviet", "awards", "medal_for_the_defense_of_stalingrad"):
        "Stalingrado\u2014la batalla que rompi\u00f3 el impulso estrat\u00e9gico de la Wehrmacht. "
        "Estabas en el aire sobre la ciudad mientras absorb\u00eda lo peor del enemigo. "
        "La medalla marca un momento que cambi\u00f3 la guerra entera.",

    ("narratives", "soviet", "awards", "medal_for_the_defense_of_the_caucasus"):
        "La campa\u00f1a del C\u00e1ucaso: petr\u00f3leo, pasos de monta\u00f1a "
        "y el borde de una cat\u00e1strofe que fue repelida. Volaste en las batallas "
        "que mantuvieron el combustible y el flanco sur fuera del alcance enemigo.",
}

# ---------------------------------------------------------------------------
# Russian translations
# ---------------------------------------------------------------------------
RU = {
    ("narratives", "germany", "ranks", "gefreiter"):
        "\u041f\u0435\u0440\u0432\u0430\u044f \u043b\u0430\u0448\u043a\u0430 \u0432 \u0432\u043e\u0439\u043d\u0435, \u043a\u043e\u0442\u043e\u0440\u0430\u044f \u043d\u0435 \u0436\u0434\u0451\u0442 \u0431\u0443\u043c\u0430\u0436\u043d\u043e\u0439 \u0432\u043e\u043b\u043e\u043a\u0438\u0442\u044b. "
        "\u0412\u044b \u0437\u0430\u0441\u043b\u0443\u0436\u0438\u043b\u0438 \u0434\u043e\u0441\u0442\u0430\u0442\u043e\u0447\u043d\u043e \u0434\u043e\u0432\u0435\u0440\u0438\u044f \u0434\u043b\u044f \u044d\u0442\u043e\u0433\u043e \u0437\u043d\u0430\u043a\u0430 \u0440\u0430\u0437\u043b\u0438\u0447\u0438\u044f \u2014 \u0442\u0435\u043f\u0435\u0440\u044c \u0441\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u0435 \u0435\u0433\u043e.",

    ("narratives", "germany", "ranks", "fhj_oberfeldwebel"):
        "\u041a\u0430\u043d\u0434\u0438\u0434\u0430\u0442 \u0432 \u043e\u0444\u0438\u0446\u0435\u0440\u044b \u0441 \u0437\u0432\u0430\u043d\u0438\u0435\u043c \u0443\u043d\u0442\u0435\u0440\u043e\u0444\u0438\u0446\u0435\u0440\u0430 \u2014 \u0436\u0434\u0451\u0442\u0435 \u043f\u0430\u0442\u0435\u043d\u0442\u0430, "
        "\u043d\u043e \u043b\u0435\u0442\u0430\u0435\u0442\u0435 \u0442\u0430\u043a, \u0431\u0443\u0434\u0442\u043e \u043e\u043d \u0443\u0436\u0435 \u0435\u0441\u0442\u044c. \u0411\u0443\u043c\u0430\u0433\u0438 \u0432\u0430\u0441 \u0434\u043e\u0433\u043e\u043d\u044f\u0442. \u041f\u0440\u043e\u0434\u043e\u043b\u0436\u0430\u0439\u0442\u0435.",

    ("narratives", "germany", "ranks", "general_der_jagdflieger"):
        "\u0412\u044b \u0440\u0443\u043a\u043e\u0432\u043e\u0434\u0438\u0442\u0435 \u0432\u0441\u0435\u0439 \u0438\u0441\u0442\u0440\u0435\u0431\u0438\u0442\u0435\u043b\u044c\u043d\u043e\u0439 \u0430\u0432\u0438\u0430\u0446\u0438\u0435\u0439. \u041e\u043f\u0435\u0440\u0430\u0442\u0438\u0432\u043d\u044b\u0435 "
        "\u043f\u0440\u0438\u043e\u0440\u0438\u0442\u0435\u0442\u044b, \u0434\u0438\u0441\u043b\u043e\u043a\u0430\u0446\u0438\u044f \u0447\u0430\u0441\u0442\u0435\u0439, \u0434\u043e\u043a\u0442\u0440\u0438\u043d\u0430 \u043f\u043e\u0434 \u043e\u0433\u043d\u0451\u043c \u2014 \u044d\u0442\u043e \u0432\u0430\u0448\u0438 "
        "\u0438\u043d\u0441\u0442\u0440\u0443\u043c\u0435\u043d\u0442\u044b. \u041d\u0435\u0431\u043e \u043f\u0440\u0438\u043d\u0430\u0434\u043b\u0435\u0436\u0438\u0442 \u043b\u044e\u0434\u044f\u043c, \u043a\u043e\u0442\u043e\u0440\u044b\u0445 \u0432\u044b \u0442\u0443\u0434\u0430 \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u044f\u0435\u0442\u0435.",

    ("narratives", "britain", "ranks", "corporal"):
        "\u0414\u0432\u0430 \u0448\u0435\u0432\u0440\u043e\u043d\u0430 \u0438 \u043c\u0430\u043b\u043e\u0435 \u043e\u0442\u0434\u0435\u043b\u0435\u043d\u0438\u0435, \u043a\u043e\u0442\u043e\u0440\u043e\u0435 \u0440\u0430\u0441\u0441\u0447\u0438\u0442\u044b\u0432\u0430\u0435\u0442 \u043d\u0430 \u0432\u0430\u0441. "
        "\u0420\u0410\u0424 \u0434\u0435\u0440\u0436\u0438\u0442\u0441\u044f \u043d\u0430 \u043b\u044e\u0434\u044f\u0445, \u043a\u043e\u0442\u043e\u0440\u044b\u0435 \u0434\u0435\u0440\u0436\u0430\u0442\u0441\u044f \u043d\u0430 \u044d\u0442\u043e\u043c \u0443\u0440\u043e\u0432\u043d\u0435. \u0411\u0443\u0434\u044c\u0442\u0435 \u044d\u0442\u0438\u043c \u0447\u0435\u043b\u043e\u0432\u0435\u043a\u043e\u043c.",

    ("narratives", "britain", "ranks", "air_marshal"):
        "\u0412\u044b \u043c\u044b\u0441\u043b\u0438\u0442\u0435 \u0432\u043e\u0437\u0434\u0443\u0448\u043d\u044b\u043c\u0438 \u043a\u0430\u043c\u043f\u0430\u043d\u0438\u044f\u043c\u0438, \u0430 \u043d\u0435 \u0432\u044b\u043b\u0435\u0442\u0430\u043c\u0438. "
        "\u0420\u0435\u0441\u0443\u0440\u0441\u044b, \u0441\u0442\u0440\u0430\u0442\u0435\u0433\u0438\u044f \u0438 \u043f\u043e\u043b\u0438\u0442\u0438\u043a\u0430 \u043d\u0430 \u0432\u044b\u0441\u0448\u0435\u043c \u0443\u0440\u043e\u0432\u043d\u0435. "
        "\u0412\u044b, \u0432\u043e\u0437\u043c\u043e\u0436\u043d\u043e, \u0435\u0449\u0451 \u043b\u0435\u0442\u0430\u0435\u0442\u0435 \u2014 \u043d\u043e \u0432\u043e\u0439\u043d\u0430 \u0438\u0434\u0451\u0442 \u0447\u0435\u0440\u0435\u0437 \u0432\u0430\u0448\u0438 \u0440\u0435\u0448\u0435\u043d\u0438\u044f.",

    ("narratives", "britain", "ranks", "air_chief_marshal"):
        "\u0412\u0435\u0440\u0448\u0438\u043d\u0430 \u043e\u043f\u0435\u0440\u0430\u0442\u0438\u0432\u043d\u043e\u0433\u043e \u0437\u0432\u0430\u043d\u0438\u044f. \u0422\u043e, \u0447\u0442\u043e \u0432\u044b \u0440\u0435\u0448\u0430\u0435\u0442\u0435, "
        "\u043e\u043f\u0440\u0435\u0434\u0435\u043b\u044f\u0435\u0442 \u0432\u043e\u0437\u0434\u0443\u0448\u043d\u0443\u044e \u0432\u043e\u0439\u043d\u0443. \u041a\u0430\u0436\u0434\u043e\u0435 \u0430\u0432\u0438\u0430\u043a\u0440\u044b\u043b\u043e \u0420\u0410\u0424 \u0432 \u0442\u0435\u0430\u0442\u0440\u0435 "
        "\u043e\u0442\u0432\u0435\u0447\u0430\u0435\u0442 \u043f\u043e \u0446\u0435\u043f\u043e\u0447\u043a\u0435, \u043a\u043e\u0442\u043e\u0440\u0430\u044f \u043a\u043e\u043d\u0447\u0430\u0435\u0442\u0441\u044f \u0437\u0434\u0435\u0441\u044c.",

    ("narratives", "soviet", "ranks", "efreitor"):
        "\u041d\u0430 \u043e\u0434\u043d\u0443 \u0441\u0442\u0443\u043f\u0435\u043d\u044c\u043a\u0443 \u0432\u044b\u0448\u0435 \u043d\u0438\u0437\u0430. \u041b\u044b\u0447\u043a\u0430 \u0441\u043a\u0440\u043e\u043c\u043d\u0430\u044f \u2014 \u0442\u0440\u0435\u0431\u043e\u0432\u0430\u043d\u0438\u044f \u0442\u043e\u043b\u044c\u043a\u043e "
        "\u0447\u0442\u043e \u0432\u044b\u0440\u043e\u0441\u043b\u0438. \u0412\u044b\u0445\u043e\u0434\u0438\u0442\u0435, \u0434\u0435\u0440\u0436\u0438\u0442\u0435 \u043f\u043e\u0437\u0438\u0446\u0438\u044e, \u043d\u0435 \u0434\u043e\u0431\u0430\u0432\u043b\u044f\u0439\u0442\u0435 \u0437\u0430\u0431\u043e\u0442 \u043e\u043a\u0440\u0443\u0436\u0430\u044e\u0449\u0438\u043c. \u042d\u0442\u043e \u0438 \u0435\u0441\u0442\u044c \u0441\u043b\u0443\u0436\u0431\u0430.",

    ("narratives", "soviet", "ranks", "mladshiy_serzhant"):
        "\u041c\u043b\u0430\u0434\u0448\u0438\u0439 \u0441\u0435\u0440\u0436\u0430\u043d\u0442. \u0417\u0432\u0430\u043d\u0438\u0435 \u043d\u0435\u0432\u0435\u043b\u0438\u043a\u043e, \u043d\u043e \u0440\u043e\u043b\u044c \u043d\u0430\u0441\u0442\u043e\u044f\u0449\u0430\u044f. "
        "\u0421\u0435\u0439\u0447\u0430\u0441 \u043a\u0442\u043e-\u0442\u043e \u043d\u0430\u0431\u043b\u044e\u0434\u0430\u0435\u0442, \u043a\u0430\u043a \u0432\u044b \u0434\u0435\u0440\u0436\u0438\u0442\u0435\u0441\u044c \u043f\u043e\u0434 \u0434\u0430\u0432\u043b\u0435\u043d\u0438\u0435\u043c. \u041d\u0435 \u043f\u043e\u0434\u0432\u0435\u0434\u0438\u0442\u0435 \u0435\u0433\u043e.",

    ("narratives", "soviet", "ranks", "general_polkovnik"):
        "\u041a\u043e\u043c\u0430\u043d\u0434\u043e\u0432\u0430\u043d\u0438\u0435 \u043d\u0430 \u0443\u0440\u043e\u0432\u043d\u0435 \u0430\u0440\u043c\u0438\u0439. \u0412\u044b \u043a\u043e\u043e\u0440\u0434\u0438\u043d\u0438\u0440\u0443\u0435\u0442\u0435 \u0444\u0440\u043e\u043d\u0442\u044b, "
        "\u0440\u0430\u0441\u043f\u0440\u0435\u0434\u0435\u043b\u044f\u0435\u0442\u0435 \u0432\u043e\u0437\u0434\u0443\u0448\u043d\u044b\u0435 \u0430\u0440\u043c\u0438\u0438 \u0438 \u043e\u0442\u0447\u0438\u0442\u044b\u0432\u0430\u0435\u0442\u0435\u0441\u044c \u043f\u0435\u0440\u0435\u0434 \u0421\u0442\u0430\u0432\u043a\u043e\u0439. "
        "\u041e\u0442\u0434\u0435\u043b\u044c\u043d\u044b\u0435 \u0441\u0430\u043c\u043e\u043b\u0451\u0442\u044b \u2014 \u044d\u0442\u043e \u0430\u0431\u0441\u0442\u0440\u0430\u043a\u0446\u0438\u044f; \u0432\u044b \u0434\u0432\u0438\u0436\u0435\u0442\u0435 \u0432\u0435\u0441\u044c \u0438\u043d\u0441\u0442\u0440\u0443\u043c\u0435\u043d\u0442 \u0432\u043e\u0437\u0434\u0443\u0448\u043d\u043e\u0439 \u043c\u043e\u0449\u0438.",

    ("narratives", "usa", "ranks", "staff_sergeant"):
        "\u0422\u0440\u0438 \u0437\u043d\u0430\u0448\u0438\u0432\u043a\u0430 \u0432\u0432\u0435\u0440\u0445\u0443, \u0434\u0432\u0435 \u0432\u043d\u0438\u0437\u0443. \u0412\u044b \u2014 \u0438\u043d\u0441\u0442\u0438\u0442\u0443\u0446\u0438\u043e\u043d\u0430\u043b\u044c\u043d\u0430\u044f \u043f\u0430\u043c\u044f\u0442\u044c "
        "\u0441\u0432\u043e\u0435\u0439 \u0447\u0430\u0441\u0442\u0438 \u0438 \u043e\u0441\u043d\u043e\u0432\u0430 \u0435\u0451 \u0434\u0438\u0441\u0446\u0438\u043f\u043b\u0438\u043d\u044b. \u041e\u0444\u0438\u0446\u0435\u0440\u044b \u0437\u0430\u0434\u0430\u044e\u0442 \u043d\u0430\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u0435\u2014\u0432\u044b \u0435\u0433\u043e \u043e\u0431\u0435\u0441\u043f\u0435\u0447\u0438\u0432\u0430\u0435\u0442\u0435.",

    ("narratives", "usa", "ranks", "technical_sergeant"):
        "\u0422\u0435\u0445\u043d\u0438\u0447\u0435\u0441\u043a\u0438\u0439 \u0441\u0435\u0440\u0436\u0430\u043d\u0442. \u0412\u044b \u0434\u0435\u0440\u0436\u0438\u0442\u0435 \u0442\u0435\u0445\u043d\u0438\u043a\u0443 \u0432 \u0438\u0441\u043f\u0440\u0430\u0432\u043d\u043e\u043c \u0441\u043e\u0441\u0442\u043e\u044f\u043d\u0438\u0438 "
        "\u0438 \u044d\u043a\u0438\u043f\u0430\u0436\u0438 \u043d\u0430\u0447\u0435\u043a\u0443. \u0422\u043e, \u0447\u0442\u043e \u0432\u044b \u0437\u043d\u0430\u0435\u0442\u0435 \u043e\u0431 \u044d\u0442\u043e\u043c \u0441\u0430\u043c\u043e\u043b\u0451\u0442\u0435, \u0434\u0435\u0440\u0436\u0438\u0442 \u0435\u0433\u043e \u0432 \u0432\u043e\u0437\u0434\u0443\u0445\u0435 \u0438 \u043b\u044e\u0434\u0435\u0439 \u0436\u0438\u0432\u044b\u043c\u0438.",

    ("narratives", "usa", "ranks", "lieutenant_general"):
        "\u0422\u0440\u0438 \u0437\u0432\u0435\u0437\u0434\u044b. \u0412\u044b \u043f\u0440\u043e\u0432\u043e\u0434\u0438\u0442\u0435 \u0432\u043e\u0437\u0434\u0443\u0448\u043d\u044b\u0435 \u043a\u0430\u043c\u043f\u0430\u043d\u0438\u0438 \u043d\u0430 \u0446\u0435\u043b\u044b\u0435 \u0442\u0435\u0430\u0442\u0440\u044b "
        "\u0438 \u0444\u043e\u0440\u043c\u0438\u0440\u0443\u0435\u0442\u0435 \u0441\u0442\u0440\u0430\u0442\u0435\u0433\u0438\u044e, \u043a\u043e\u0442\u043e\u0440\u0443\u044e \u044d\u043a\u0438\u043f\u0430\u0436\u0438 \u0432\u044b\u043f\u043e\u043b\u043d\u044f\u044e\u0442 \u043d\u0430 \u0432\u044b\u0441\u043e\u0442\u0435. "
        "\u041b\u044e\u0434\u0438 \u043d\u0430 \u043f\u0435\u0440\u0435\u0434\u043e\u0432\u043e\u0439 \u0434\u0430\u043b\u0435\u043a\u043e\u2014\u043d\u043e \u043a\u0430\u0436\u0434\u043e\u0435 \u0432\u0430\u0448\u0435 \u0440\u0435\u0448\u0435\u043d\u0438\u0435 \u043e\u0442\u0437\u044b\u0432\u0430\u0435\u0442\u0441\u044f \u0432 \u043d\u0435\u0431\u0435 \u043d\u0430\u0434 \u043d\u0438\u043c\u0438.",

    ("narratives", "britain", "awards", "third_bar_to_the_distinguished_service_order"):
        "\u0422\u0440\u0435\u0442\u044c\u044f \u043f\u043b\u0430\u043d\u043a\u0430 \u043a \u041e\u0440\u0434\u0435\u043d\u0443 \u043e\u0442\u043b\u0438\u0447\u043d\u043e\u0439 \u0441\u043b\u0443\u0436\u0431\u044b. \u0422\u0440\u0438 \u043e\u0442\u0434\u0435\u043b\u044c\u043d\u044b\u0445 \u043d\u0430\u0433\u0440\u0430\u0436\u0434\u0435\u043d\u0438\u044f, "
        "\u043a\u0430\u0436\u0434\u043e\u0435 \u0438\u0437 \u043a\u043e\u0442\u043e\u0440\u044b\u0445 \u043f\u0440\u0435\u0434\u044a\u044f\u0432\u043b\u044f\u043b\u043e \u0442\u0440\u0435\u0431\u043e\u0432\u0430\u043d\u0438\u044f, \u043d\u0435\u0434\u043e\u0441\u0442\u0438\u0436\u0438\u043c\u044b\u0435 \u0434\u043b\u044f \u0431\u043e\u043b\u044c\u0448\u0438\u043d\u0441\u0442\u0432\u0430 \u043e\u0444\u0438\u0446\u0435\u0440\u043e\u0432. "
        "\u041b\u0435\u043d\u0442\u0430 \u0441\u0442\u0430\u043b\u0430 \u0434\u043b\u0438\u043d\u043d\u0435\u0435\u2014\u0438 \u043e\u0436\u0438\u0434\u0430\u043d\u0438\u044f \u0442\u043e\u0436\u0435.",

    ("narratives", "britain", "awards", "france_and_germany_star"):
        "\u041f\u043e\u0441\u043b\u0435\u0434\u043d\u044f\u044f \u043a\u0430\u043c\u043f\u0430\u043d\u0438\u044f. \u041e\u0442 \u041d\u043e\u0440\u043c\u0430\u043d\u0434\u0438\u0438 \u0434\u043e \u0420\u0435\u0439\u0445\u0430\u2014\u0432\u044b \u043b\u0435\u0442\u0435\u043b\u0438, "
        "\u043a\u043e\u0433\u0434\u0430 \u0432\u043e\u0439\u043d\u0430 \u0432 \u0417\u0430\u043f\u0430\u0434\u043d\u043e\u0439 \u0415\u0432\u0440\u043e\u043f\u0435 \u043f\u0440\u0438\u0448\u043b\u0430 \u043a \u0437\u0430\u0432\u0435\u0440\u0448\u0435\u043d\u0438\u044e. "
        "\u0417\u0432\u0435\u0437\u0434\u0430 \u043e\u0437\u043d\u0430\u0447\u0430\u0435\u0442 \u043f\u0443\u0442\u044c, \u043a\u043e\u0442\u043e\u0440\u044b\u0439 \u0437\u0430\u043a\u043e\u043d\u0447\u0438\u043b\u0441\u044f \u0432 \u043d\u0435\u043c\u0435\u0446\u043a\u043e\u043c \u0432\u043e\u0437\u0434\u0443\u0448\u043d\u043e\u043c \u043f\u0440\u043e\u0441\u0442\u0440\u0430\u043d\u0441\u0442\u0432\u0435.",

    ("narratives", "usa", "awards", "air_medal_plus_four_oak_leaf_clusters"):
        "\u041f\u044f\u0442\u044c \u043d\u0430\u0433\u0440\u0430\u0436\u0434\u0435\u043d\u0438\u0439 \u0437\u0430 \u0431\u043e\u0435\u0432\u044b\u0435 \u0432\u044b\u043b\u0435\u0442\u044b. "
        "\u041a\u043b\u0430\u0441\u0442\u0435\u0440\u044b \u2014 \u044d\u0442\u043e \u0430\u0440\u0438\u0444\u043c\u0435\u0442\u0438\u043a\u0430 \u0432\u043e\u0439\u043d\u044b: "
        "\u0431\u043e\u043b\u044c\u0448\u0435 \u0432\u044b\u043b\u0435\u0442\u043e\u0432, \u0431\u043e\u043b\u044c\u0448\u0435 \u0440\u0438\u0441\u043a\u0430, \u0442\u043e \u0436\u0435 \u043d\u0435\u0431\u043e, \u043a\u043e\u0442\u043e\u0440\u043e\u0435 \u043d\u0435 \u0441\u0442\u0430\u043d\u043e\u0432\u0438\u0442\u0441\u044f \u0431\u0435\u0437\u043e\u043f\u0430\u0441\u043d\u0435\u0435.",

    ("narratives", "usa", "awards", "air_medal_plus_one_silver_leaf_cluster"):
        "\u0421\u0435\u0440\u0435\u0431\u0440\u044f\u043d\u044b\u0439 \u043a\u043b\u0430\u0441\u0442\u0435\u0440 \u0432\u043c\u0435\u0441\u0442\u043e \u043f\u044f\u0442\u0438 \u0434\u043e\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u044c\u043d\u044b\u0445 \u043d\u0430\u0433\u0440\u0430\u0436\u0434\u0435\u043d\u0438\u0439. "
        "\u041b\u0435\u043d\u0442\u0430 \u043d\u0435 \u0441\u043f\u043e\u0441\u043e\u0431\u043d\u0430 \u0443\u0441\u043f\u0435\u0432\u0430\u0442\u044c \u0437\u0430 \u043c\u0438\u0441\u0441\u0438\u044f\u043c\u0438. \u0412\u044b\u043b\u0435\u0442\u044b \u043f\u0440\u043e\u0434\u043e\u043b\u0436\u0430\u043b\u0438\u0441\u044c \u0432\u0441\u0451 \u0440\u0430\u0432\u043d\u043e.",

    ("narratives", "usa", "awards", "european_african_middle_eastern_campaign_medal"):
        "\u0427\u0435\u0440\u0435\u0437 \u0442\u0435\u0430\u0442\u0440\u044b, \u043a\u043e\u0442\u043e\u0440\u044b\u0435 \u043f\u043e\u0432\u0435\u0440\u043d\u0443\u043b\u0438 \u0445\u043e\u0434 \u0432\u043e\u0439\u043d\u044b. "
        "\u0421\u0435\u0432\u0435\u0440\u043d\u0430\u044f \u0410\u0444\u0440\u0438\u043a\u0430, \u0421\u0440\u0435\u0434\u0438\u0437\u0435\u043c\u043d\u043e\u043c\u043e\u0440\u044c\u0435, \u043f\u043e\u0434\u0445\u043e\u0434\u044b \u043a \u0415\u0432\u0440\u043e\u043f\u0435 \u2014 \u0432\u044b \u0431\u044b\u043b\u0438 \u0437\u0434\u0435\u0441\u044c, "
        "\u043f\u043e\u043a\u0430 \u0441\u0442\u0440\u0430\u0442\u0435\u0433\u0438\u0447\u0435\u0441\u043a\u0438\u0439 \u0431\u0430\u043b\u0430\u043d\u0441 \u0441\u043c\u0435\u0449\u0430\u043b\u0441\u044f.",

    ("narratives", "soviet", "awards", "aircraft_kill_bonus_1000_rubles"):
        "\u0413\u043e\u0441\u0443\u0434\u0430\u0440\u0441\u0442\u0432\u043e \u043f\u043b\u0430\u0442\u0438\u0442 \u0437\u0430 \u043f\u043e\u0431\u0435\u0434\u044b. \u0422\u044b\u0441\u044f\u0447\u0430 \u0440\u0443\u0431\u043b\u0435\u0439 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0430\u0435\u0442, "
        "\u0447\u0442\u043e \u0432\u044b \u043f\u0440\u0438\u0446\u0435\u043b\u0438\u043b\u0438\u0441\u044c, \u043f\u043e\u043f\u0430\u043b\u0438 \u0438 \u0443\u0431\u0440\u0430\u043b\u0438 \u0441\u0430\u043c\u043e\u043b\u0451\u0442 \u0438\u0437 \u0441\u0447\u0451\u0442\u0430 \u043f\u0440\u043e\u0442\u0438\u0432\u043d\u0438\u043a\u0430.",

    ("narratives", "soviet", "awards", "fighter_kill_bonus_1000_rubles"):
        "\u0418\u0441\u0442\u0440\u0435\u0431\u0438\u0442\u0435\u043b\u044c \u0441\u0431\u0438\u0442. \u0423\u0433\u0440\u043e\u0437\u0430 \u0443\u0441\u0442\u0440\u0430\u043d\u0435\u043d\u0430\u2014\u043f\u043b\u0430\u0442\u0451\u0436 \u0441\u043b\u0435\u0434\u0443\u0435\u0442. "
        "\u0422\u044b\u0441\u044f\u0447\u0430 \u0440\u0443\u0431\u043b\u0435\u0439 \u0437\u0430 \u043f\u043e\u0431\u0435\u0434\u0443, \u043a\u043e\u0442\u043e\u0440\u0430\u044f, \u0432\u043e\u0437\u043c\u043e\u0436\u043d\u043e, \u0441\u043f\u0430\u0441\u043b\u0430 \u0432\u0435\u0434\u043e\u043c\u043e\u0433\u043e.",

    ("narratives", "soviet", "awards", "transport_plane_kill_bonus_1500_rubles"):
        "\u0422\u0440\u0430\u043d\u0441\u043f\u043e\u0440\u0442 \u0443\u0431\u0440\u0430\u043d \u0438\u0437 \u043b\u043e\u0433\u0438\u0441\u0442\u0438\u0447\u0435\u0441\u043a\u043e\u0433\u043e \u0443\u0440\u0430\u0432\u043d\u0435\u043d\u0438\u044f. "
        "\u041f\u044f\u0442\u043d\u0430\u0434\u0446\u0430\u0442\u044c \u0441\u043e\u0442 \u0440\u0443\u0431\u043b\u0435\u0439 \u0437\u0430 \u043e\u0431\u0440\u044b\u0432 \u043d\u0438\u0442\u0438, \u043d\u0430 \u043a\u043e\u0442\u043e\u0440\u0443\u044e \u0440\u0430\u0441\u0441\u0447\u0438\u0442\u044b\u0432\u0430\u043b \u043f\u0440\u043e\u0442\u0438\u0432\u043d\u0438\u043a.",

    ("narratives", "soviet", "awards", "bomber_kill_bonus_1500_rubles"):
        "\u0411\u043e\u043c\u0431\u0430\u0440\u0434\u0438\u0440\u043e\u0432\u0449\u0438\u043a \u043f\u0435\u0440\u0435\u0445\u0432\u0430\u0447\u0435\u043d \u0434\u043e \u0446\u0435\u043b\u0438. "
        "\u041f\u044f\u0442\u043d\u0430\u0434\u0446\u0430\u0442\u044c \u0441\u043e\u0442 \u0440\u0443\u0431\u043b\u0435\u0439 \u0437\u0430 \u043c\u0438\u0441\u0441\u0438\u044e, \u043a\u043e\u0442\u043e\u0440\u0443\u044e \u043e\u043d \u0442\u0430\u043a \u0438 \u043d\u0435 \u0432\u044b\u043f\u043e\u043b\u043d\u0438\u043b.",

    ("narratives", "soviet", "awards", "bomber_kill_bonus_2000_rubles"):
        "\u0415\u0449\u0451 \u043e\u0434\u0438\u043d \u0431\u043e\u043c\u0431\u0430\u0440\u0434\u0438\u0440\u043e\u0432\u0449\u0438\u043a \u0432\u044b\u0447\u0435\u0440\u043a\u043d\u0443\u0442 \u0438\u0437 \u0431\u043e\u0435\u0432\u043e\u0433\u043e \u0440\u0430\u0441\u043f\u0438\u0441\u0430\u043d\u0438\u044f. "
        "\u041f\u0440\u0435\u043c\u0438\u044f \u043e\u0442\u0440\u0430\u0436\u0430\u0435\u0442 \u0443\u0440\u043e\u0432\u0435\u043d\u044c \u0443\u0433\u0440\u043e\u0437\u044b. "
        "\u0414\u0432\u0435 \u0442\u044b\u0441\u044f\u0447\u0438 \u0440\u0443\u0431\u043b\u0435\u0439 \u0437\u0430 \u0441\u043e\u0445\u0440\u0430\u043d\u043d\u043e\u0441\u0442\u044c \u0442\u043e\u0433\u043e, \u0447\u0442\u043e \u0432\u043d\u0438\u0437\u0443.",

    ("narratives", "soviet", "awards", "small_ship_kill_bonus_1000_rubles"):
        "\u041c\u0430\u043b\u043e\u0435 \u0441\u0443\u0434\u043d\u043e \u0432\u044b\u0432\u0435\u0434\u0435\u043d\u043e \u0438\u0437 \u0441\u0442\u0440\u043e\u044f. \u041f\u0440\u0435\u043c\u0438\u044f \u0441\u043a\u0440\u043e\u043c\u043d\u0430\u044f\u2014"
        "\u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442, \u043e\u0434\u043d\u0438\u043c \u0432\u0440\u0430\u0436\u0435\u0441\u043a\u0438\u043c \u0430\u043a\u0442\u0438\u0432\u043e\u043c \u043c\u0435\u043d\u044c\u0448\u0435 \u043d\u0430 \u0432\u043e\u0434\u0435, \u043d\u0435\u0442.",

    ("narratives", "soviet", "awards", "transport_ship_kill_bonus_3000_rubles"):
        "\u0422\u0440\u0430\u043d\u0441\u043f\u043e\u0440\u0442\u043d\u043e\u0435 \u0441\u0443\u0434\u043d\u043e \u2014 \u044d\u0442\u043e \u043d\u0435 \u043f\u0440\u043e\u0441\u0442\u043e \u0446\u0435\u043b\u044c, \u044d\u0442\u043e \u0446\u0435\u043f\u044c \u0441\u043d\u0430\u0431\u0436\u0435\u043d\u0438\u044f. "
        "\u0422\u0440\u0438 \u0442\u044b\u0441\u044f\u0447\u0438 \u0440\u0443\u0431\u043b\u0435\u0439, \u043f\u043e\u0442\u043e\u043c\u0443 \u0447\u0442\u043e \u0442\u043e, \u0447\u0442\u043e \u043e\u043d\u043e \u0432\u0435\u0437\u043b\u043e, \u0442\u0430\u043a \u0438 \u043d\u0435 \u0434\u043e\u0441\u0442\u0430\u0432\u043b\u0435\u043d\u043e.",

    ("narratives", "soviet", "awards", "destroyer_or_submarine_kill_bonus_10000_rubles"):
        "\u0412\u043e\u0435\u043d\u043d\u044b\u0439 \u043a\u043e\u0440\u0430\u0431\u043b\u044c \u2014 \u044d\u0441\u043c\u0438\u043d\u0435\u0446 \u0438\u043b\u0438 \u043f\u043e\u0434\u0432\u043e\u0434\u043d\u0430\u044f \u043b\u043e\u0434\u043a\u0430. "
        "\u0414\u0435\u0441\u044f\u0442\u044c \u0442\u044b\u0441\u044f\u0447 \u0440\u0443\u0431\u043b\u0435\u0439, \u043f\u043e\u0442\u043e\u043c\u0443 \u0447\u0442\u043e \u0443\u0433\u0440\u043e\u0437\u0430 \u0434\u043b\u044f \u0441\u0432\u043e\u0438\u0445 \u0441\u0438\u043b \u0438 \u043b\u0438\u043d\u0438\u0439 \u0441\u043d\u0430\u0431\u0436\u0435\u043d\u0438\u044f "
        "\u0431\u044b\u043b\u0430 \u0441\u043e\u043e\u0442\u0432\u0435\u0442\u0441\u0442\u0432\u0435\u043d\u043d\u043e \u0441\u0435\u0440\u044c\u0451\u0437\u043d\u043e\u0439. \u041e\u043d\u043e \u043d\u0435 \u0432\u0435\u0440\u043d\u0451\u0442\u0441\u044f.",

    ("narratives", "soviet", "awards", "medal_for_the_defense_of_moscow"):
        "\u0421\u0430\u043c\u0430 \u041c\u043e\u0441\u043a\u0432\u0430 \u0431\u044b\u043b\u0430 \u043f\u043e\u0434 \u0432\u043e\u043f\u0440\u043e\u0441\u043e\u043c. \u0412\u044b \u043b\u0435\u0442\u0435\u043b\u0438 \u043d\u0430\u0434 \u0433\u043e\u0440\u043e\u0434\u043e\u043c, "
        "\u043a\u043e\u0442\u043e\u0440\u044b\u0439 \u043d\u0435 \u0438\u043c\u0435\u043b \u043f\u0440\u0430\u0432\u0430 \u0443\u043f\u0430\u0441\u0442\u044c\u2014\u0438 \u043e\u043d \u0443\u0441\u0442\u043e\u044f\u043b. "
        "\u042d\u0442\u0430 \u043c\u0435\u0434\u0430\u043b\u044c \u2014 \u043f\u0430\u043c\u044f\u0442\u044c \u043e \u0441\u0440\u0430\u0436\u0435\u043d\u0438\u0438, \u043a\u043e\u0442\u043e\u0440\u043e\u0435 \u0434\u0435\u0440\u0436\u0430\u043b\u043e \u0432\u043e\u0439\u043d\u0443 \u0436\u0438\u0432\u043e\u0439.",

    ("narratives", "soviet", "awards", "medal_for_the_defense_of_stalingrad"):
        "\u0421\u0442\u0430\u043b\u0438\u043d\u0433\u0440\u0430\u0434\u2014\u0441\u0440\u0430\u0436\u0435\u043d\u0438\u0435, \u0441\u043b\u043e\u043c\u0430\u0432\u0448\u0435\u0435 \u0441\u0442\u0440\u0430\u0442\u0435\u0433\u0438\u0447\u0435\u0441\u043a\u0438\u0439 \u0438\u043c\u043f\u0443\u043b\u044c\u0441 \u0432\u0435\u0440\u043c\u0430\u0445\u0442\u0430. "
        "\u0412\u044b \u043b\u0435\u0442\u0435\u043b\u0438 \u043d\u0430\u0434 \u0433\u043e\u0440\u043e\u0434\u043e\u043c, \u043f\u043e\u043a\u0430 \u043e\u043d \u043f\u0440\u0438\u043d\u0438\u043c\u0430\u043b \u0432\u0441\u0451 \u0441\u0430\u043c\u043e\u0435 \u0441\u0442\u0440\u0430\u0448\u043d\u043e\u0435 \u043e\u0442 \u0432\u0440\u0430\u0433\u0430. "
        "\u041c\u0435\u0434\u0430\u043b\u044c \u043e\u0437\u043d\u0430\u0447\u0430\u0435\u0442 \u043c\u043e\u043c\u0435\u043d\u0442, \u0438\u0437\u043c\u0435\u043d\u0438\u0432\u0448\u0438\u0439 \u0432\u0441\u044e \u0432\u043e\u0439\u043d\u0443.",

    ("narratives", "soviet", "awards", "medal_for_the_defense_of_the_caucasus"):
        "\u041a\u0430\u0432\u043a\u0430\u0437\u0441\u043a\u0430\u044f \u043a\u0430\u043c\u043f\u0430\u043d\u0438\u044f\u2014\u043d\u0435\u0444\u0442\u044c, \u0433\u043e\u0440\u043d\u044b\u0435 \u043f\u0435\u0440\u0435\u0432\u0430\u043b\u044b \u0438 \u043a\u0440\u0430\u0439 \u043a\u0430\u0442\u0430\u0441\u0442\u0440\u043e\u0444\u044b, "
        "\u043a\u043e\u0442\u043e\u0440\u0430\u044f \u0431\u044b\u043b\u0430 \u043e\u0442\u043e\u0433\u043d\u0430\u043d\u0430. \u0412\u044b \u043b\u0435\u0442\u0435\u043b\u0438 \u0432 \u0441\u0440\u0430\u0436\u0435\u043d\u0438\u044f\u0445, \u0443\u0434\u0435\u0440\u0436\u0430\u0432\u0448\u0438\u0445 "
        "\u0442\u043e\u043f\u043b\u0438\u0432\u043e \u0438 \u044e\u0436\u043d\u044b\u0439 \u0444\u043b\u0430\u043d\u0433 \u043e\u0442 \u0432\u0440\u0430\u0433\u0430.",
}

# Polish, Chinese — stub with English (same quality bar; translators can refine)
PL = {k: v for k, v in EN.items()}
ZH = {k: v for k, v in EN.items()}

# Override a few Polish keys with natural Polish phrasing
PL.update({
    ("narratives", "germany", "ranks", "gefreiter"):
        "Twoja pierwsza lampaska w wojnie, kt\u00f3ra nie czeka na papiery. "
        "Zas\u0142u\u017cy\u0142e\u015b na ten sznur\u2014teraz go utrzymaj.",

    ("narratives", "germany", "ranks", "fhj_oberfeldwebel"):
        "Kandydat na oficera z rang\u0105 podoficera \u2014 czekasz na mianowanie, "
        "a lataasz jakby\u015b je ju\u017c mia\u0142. Papiery ci\u0119 dogoni\u0105. Kontynuuj.",

    ("narratives", "germany", "ranks", "general_der_jagdflieger"):
        "Dowodzisz ca\u0142ym lotnictwem my\u015bliwskim. Priorytety operacyjne, "
        "rozmieszczenie jednostek, doktryna pod ostrza\u0142em \u2014 to teraz twoje narz\u0119dzia. "
        "Niebo nale\u017cy do ludzi, kt\u00f3rych tam wysy\u0142asz.",

    ("narratives", "soviet", "ranks", "efreitor"):
        "Jeden szczebel wy\u017cej od dna. Lampaska ma\u0142a \u2014 oczekiwania w\u0142a\u015bnie wzros\u0142y. "
        "Staw si\u0119, utrzymaj lini\u0119, nie ko\u015btuj nikomu dodatkowego wysi\u0142ku. To jest s\u0142u\u017cba.",

    ("narratives", "soviet", "ranks", "mladshiy_serzhant"):
        "M\u0142odszy sier\u017cant. Tytu\u0142 skromny, ale rola prawdziwa. "
        "Kto\u015b obserwuje teraz, jak radzisz sobie z presj\u0105. Nie zawied\u017a go.",

    ("narratives", "soviet", "ranks", "general_polkovnik"):
        "Dow\u00f3dztwo na szczeblu armii. Koordynujesz fronty, przydzielasz armie lotnicze "
        "i odpowiadasz przed Stawka. Poszczeg\u00f3lne samoloty to abstrakcja\u2014poruszasz "
        "ca\u0142ym instrumentem pot\u0119gi powietrznej.",

    ("narratives", "soviet", "awards", "medal_for_the_defense_of_moscow"):
        "Sama Moskwa by\u0142a zagrożona. Lata\u0142e\u015b nad miastem, kt\u00f3re nie mog\u0142o upa\u015b\u0107\u2014"
        "i nie upad\u0142o. Ten medal utrwala bitw\u0119, kt\u00f3ra utrzyma\u0142a wojn\u0119 przy \u017cyciu.",

    ("narratives", "soviet", "awards", "medal_for_the_defense_of_stalingrad"):
        "Stalingrad \u2014 bitwa, kt\u00f3ra z\u0142ama\u0142a strategiczny impet Wehrmachtu. "
        "By\u0142e\u015b w powietrzu nad miastem, kt\u00f3re ch\u0142on\u0119\u0142o najgorsze, co m\u00f3g\u0142 pos\u0142a\u0107 wrog. "
        "Medal oznacza moment, kt\u00f3ry zmieni\u0142 ca\u0142\u0105 wojn\u0119.",

    ("narratives", "soviet", "awards", "medal_for_the_defense_of_the_caucasus"):
        "Kampania kaukaska \u2014 ropa, prze\u0142\u0119cze i kr\u0105g katastrofy, kt\u00f3ra zosta\u0142a "
        "odepchni\u0119ta. Lata\u0142e\u015b w bitwach, kt\u00f3re uratowa\u0142y paliwo i po\u0142udniow\u0105 "
        "flank\u0119 przed wrogiem.",
})

# Chinese: short, evocative two-sentence forms
ZH.update({
    ("narratives", "germany", "ranks", "gefreiter"):
        "\u7b2c\u4e00\u6761\u8962\u7ae0\u2014\u8fd9\u573a\u6218\u4e89\u4e0d\u7b49\u4e3b\u4e49\u6587\u5c71\u3002"
        "\u4f60\u5df2\u8d62\u5f97\u4fe1\u4efb\uff0c\u73b0\u5728\u8981\u5b88\u4f4f\u5b83\u3002",

    ("narratives", "germany", "ranks", "fhj_oberfeldwebel"):
        "\u5b98\u5019\u751f\u5f85\u7206\uff0c\u5374\u5df2\u50cf\u8001\u624b\u4e00\u6837\u98de\u884c\u3002"
        "\u6587\u4ef6\u4f1a\u8ffd\u4e0a\u4f60\u7684\u3002",

    ("narratives", "germany", "ranks", "general_der_jagdflieger"):
        "\u6267\u6389\u6574\u4e2a\u6218\u6597\u673a\u96c6\u56e2\u7684\u6307\u6325\u68d2\u3002"
        "\u5929\u7a7a\u5c5e\u4e8e\u4f60\u6d3e\u51fa\u53bb\u7684\u4eba\u3002",

    ("narratives", "soviet", "ranks", "efreitor"):
        "\u6bd4\u666e\u901a\u58eb\u9ad8\u4e00\u7ea7\uff0c\u8981\u6c42\u5374\u5927\u4e86\u4e00\u500d\u3002"
        "\u51fa\u52e4\u3001\u5b88\u5c97\u3001\u4e0d\u5360\u5c0f\u4fbf\u2014\u8fd9\u5c31\u662f\u4efb\u52a1\u3002",

    ("narratives", "soviet", "ranks", "mladshiy_serzhant"):
        "\u521d\u7ea7\u4e2d\u58eb\u3002\u6709\u4eba\u76ef\u7740\u4f60\u770b\u4f60\u5982\u4f55\u627f\u538b\u3002"
        "\u522b\u8ba9\u4ed6\u5931\u671b\u3002",

    ("narratives", "soviet", "ranks", "general_polkovnik"):
        "\u5927\u5c06\u7ea7\u6307\u6325\u5b98\uff0c\u8c03\u5ea6\u6574\u4e2a\u5c40\u9762\u7684\u7a7a\u4e2d\u529b\u91cf\u3002"
        "\u5355\u67b6\u98de\u673a\u662f\u62bd\u8c61\uff0c\u4f60\u638c\u63a7\u7684\u662f\u6574\u4e2a\u6218\u6597\u52a8\u4f5c\u3002",

    ("narratives", "soviet", "awards", "aircraft_kill_bonus_1000_rubles"):
        "\u51fb\u843d\u4e00\u67b6\u654c\u673a\uff0c\u56fd\u5bb6\u5956\u52b11000\u5362\u5e03\u3002"
        "\u8bc1\u660e\u4f60\u51c6\u4e86\u3001\u6253\u4e86\u3001\u629c\u9664\u4e86\u4e00\u4e2a\u5a01\u80c1\u3002",

    ("narratives", "soviet", "awards", "fighter_kill_bonus_1000_rubles"):
        "\u651f\u5c064\u51fb\u843d\uff0c\u5956\u91d11000\u5362\u5e03\u3002"
        "\u6d88\u9664\u4e86\u4e00\u4e2a\u6218\u6597\u673a\u5a01\u80c1\uff0c\u4e5f\u8bb8\u6551\u4e86\u4e00\u4e2a\u6218\u53cb\u3002",

    ("narratives", "soviet", "awards", "transport_plane_kill_bonus_1500_rubles"):
        "\u8fd0\u8f93\u673a\u51fb\u843d\uff0c\u5956\u91d11500\u5362\u5e03\u3002"
        "\u5207\u65ad\u4e86\u654c\u65b9\u4f9d\u8d56\u7684\u4e00\u6839\u8865\u7ed9\u7ebf\u3002",

    ("narratives", "soviet", "awards", "bomber_kill_bonus_1500_rubles"):
        "\u8f70\u70b8\u673a\u5728\u5230\u8fbe\u76ee\u6807\u524d\u88ab\u62e6\u622a\uff0c\u5956\u91d11500\u5362\u5e03\u3002"
        "\u7ec8\u6b62\u4e86\u5b83\u672a\u80fd\u5b8c\u6210\u7684\u4efb\u52a1\u3002",

    ("narratives", "soviet", "awards", "bomber_kill_bonus_2000_rubles"):
        "\u53c8\u4e00\u67b6\u8f70\u70b8\u673a\u88ab\u4ece\u654c\u5355\u4e2d\u5254\u9664\uff0c\u5956\u91d12000\u5362\u5e03\u3002"
        "\u5956\u91d1\u53cd\u6620\u4e86\u5a01\u80c1\u7b49\u7ea7\uff0c\u4fdd\u62a4\u4e86\u5730\u9762\u4e0a\u7684\u4e00\u5207\u3002",

    ("narratives", "soviet", "awards", "small_ship_kill_bonus_1000_rubles"):
        "\u5c0f\u8230\u51fb\u6c89\uff0c\u5956\u91d11000\u5362\u5e03\u3002"
        "\u5956\u91d1\u4e0d\u591a\uff0c\u4f46\u7ed3\u679c\u5b9e\u5728\u2014\u6d77\u9762\u4e0a\u5c11\u4e86\u4e00\u4e2a\u654c\u65b9\u8d44\u4ea7\u3002",

    ("narratives", "soviet", "awards", "transport_ship_kill_bonus_3000_rubles"):
        "\u8fd0\u8f93\u8239\u4e0d\u4ec5\u662f\u76ee\u6807\uff0c\u66f4\u662f\u4e00\u6761\u8865\u7ed9\u94fe\u3002"
        "\u5956\u91d13000\u5362\u5e03\uff0c\u56e0\u4e3a\u5b83\u88c5\u8f7d\u7684\u4e1c\u897f\u6c38\u8fdc\u6ca1\u5230\u8fbe\u3002",

    ("narratives", "soviet", "awards", "destroyer_or_submarine_kill_bonus_10000_rubles"):
        "\u9a71\u9010\u8230\u6216\u6f5c\u6c34\u8247\u2014\u91cd\u91cf\u7ea7\u76ee\u6807\u3002"
        "\u5956\u91d11\u4e07\u5362\u5e03\uff0c\u56e0\u4e3a\u5b83\u5bf9\u6211\u65b9\u9020\u6210\u7684\u5a01\u80c1\u540c\u6837\u4e25\u91cd\u3002\u5b83\u4e0d\u4f1a\u518d\u56de\u6765\u4e86\u3002",

    ("narratives", "soviet", "awards", "medal_for_the_defense_of_moscow"):
        "\u83ab\u65af\u79d1\u5df1\u5747\u9762\u4e34\u5371\u9669\u3002\u4f60\u5728\u8fd9\u5ea7\u4e0d\u80fd\u9677\u843d\u7684\u57ce\u5e02\u4e0a\u7a7a\u6267\u884c\u4efb\u52a1\u2014\u5b83\u6ca1\u6709\u9677\u843d\u3002"
        "\u8fd9\u679a\u52cb\u7ae0\u8bb0\u5f55\u4e86\u90a3\u573a\u4f7f\u6218\u4e89\u7ee7\u7eed\u7684\u6218\u5f79\u3002",

    ("narratives", "soviet", "awards", "medal_for_the_defense_of_stalingrad"):
        "\u65af\u5927\u6797\u683c\u52d2\u2014\u6298\u65ad\u5fb7\u519b\u6218\u7565\u52bf\u5934\u7684\u6218\u5f79\u3002"
        "\u4f60\u5728\u57ce\u5e02\u4e0a\u7a7a\u4e3b\u6218\uff0c\u5979\u627f\u53d7\u5e76\u5438\u6536\u4e86\u654c\u65b9\u6700\u7b38\u7684\u8fdb\u653b\u3002"
        "\u8fd9\u679a\u52cb\u7ae0\u6807\u5fd7\u7740\u6539\u53d8\u6574\u573a\u6218\u4e89\u7684\u8f6c\u6298\u70b9\u3002",

    ("narratives", "soviet", "awards", "medal_for_the_defense_of_the_caucasus"):
        "\u9ad8\u52a0\u7d22\u6218\u5f79\uff1a\u77f3\u6cb9\u3001\u5c71\u5cb3\u5c71\u53e3\u548c\u4e00\u573a\u672a\u53d1\u751f\u7684\u51c4\u60e8\u3002"
        "\u4f60\u5728\u5c06\u71c3\u6599\u4e0e\u5357\u7ffc\u5b88\u4f4f\u7684\u6218\u6597\u4e2d\u98de\u884c\u3002",
})


# ---------------------------------------------------------------------------
# Apply all translations
# ---------------------------------------------------------------------------
LANG_DATA = {
    "en": EN,
    "de": DE,
    "fr": FR,
    "es": ES,
    "ru": RU,
    "pl": PL,
    "zh": ZH,
}

report = {}
for lang, translations in LANG_DATA.items():
    data = load(lang)
    added = []
    for key_tuple, value in translations.items():
        was_added = deep_set(data, list(key_tuple), value)
        if was_added:
            added.append(".".join(key_tuple))
    if added:
        save(lang, data)
        report[lang] = added
    else:
        report[lang] = []

print("=== Part 3 narrative sync report ===")
for lang, keys in report.items():
    print(f"\n{lang}.json: {len(keys)} keys added")
    for k in sorted(keys):
        print(f"  + {k}")
