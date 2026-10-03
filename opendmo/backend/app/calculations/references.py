"""Bibliography shared by registered methods (rendered as citations and BibTeX)."""
from .base import Reference

CIFUENTES_1992 = Reference(
    key='cifuentes1992', authors='Cifuentes, M.', year=1992, entry_type='techreport',
    title='Determinación de capacidad de carga turística en áreas protegidas',
    container='Serie Técnica, Informe Técnico No. 194',
    publisher='CATIE, Turrialba, Costa Rica')

UNWTO_2004 = Reference(
    key='unwto2004', authors='World Tourism Organization', year=2004, entry_type='book',
    title='Indicators of Sustainable Development for Tourism Destinations: A Guidebook',
    publisher='UNWTO, Madrid', doi='10.18111/9789284407262')

IRTS_2008 = Reference(
    key='irts2008', authors='United Nations, & World Tourism Organization', year=2010, entry_type='book',
    title='International Recommendations for Tourism Statistics 2008',
    container='Studies in Methods, Series M No. 83/Rev.1', publisher='United Nations, New York')

SACKS_2002 = Reference(
    key='sacks2002', authors='Sacks, J.', year=2002, entry_type='book',
    title='The Money Trail: Measuring your impact on the local economy using LM3',
    publisher='New Economics Foundation, London')

ARCHER_FLETCHER_1996 = Reference(
    key='archer1996', authors='Archer, B., & Fletcher, J.', year=1996,
    title='The economic impact of tourism in the Seychelles',
    container='Annals of Tourism Research, 23(1), 32–47', doi='10.1016/0160-7383(95)00041-0')

WINTERS_1960 = Reference(
    key='winters1960', authors='Winters, P. R.', year=1960,
    title='Forecasting sales by exponentially weighted moving averages',
    container='Management Science, 6(3), 324–342', doi='10.1287/mnsc.6.3.324')

HOLT_2004 = Reference(
    key='holt2004', authors='Holt, C. C.', year=2004,
    title='Forecasting seasonals and trends by exponentially weighted moving averages',
    container='International Journal of Forecasting, 20(1), 5–10', doi='10.1016/j.ijforecast.2003.09.015')

FPP3 = Reference(
    key='hyndman2021', authors='Hyndman, R. J., & Athanasopoulos, G.', year=2021, entry_type='book',
    title='Forecasting: Principles and Practice (3rd ed.)', publisher='OTexts, Melbourne',
    url='https://otexts.com/fpp3/')

HYNDMAN_KOEHLER_2006 = Reference(
    key='hyndman2006', authors='Hyndman, R. J., & Koehler, A. B.', year=2006,
    title='Another look at measures of forecast accuracy',
    container='International Journal of Forecasting, 22(4), 679–688', doi='10.1016/j.ijforecast.2006.03.001')

SAATY_1980 = Reference(
    key='saaty1980', authors='Saaty, T. L.', year=1980, entry_type='book',
    title='The Analytic Hierarchy Process', publisher='McGraw-Hill, New York')

AHMED_DEWAN_2017 = Reference(
    key='ahmed2017', authors='Ahmed, B., & Dewan, A.', year=2017,
    title='Application of bivariate and multivariate statistical techniques in landslide '
          'susceptibility modeling in Chittagong City Corporation, Bangladesh',
    container='Remote Sensing, 9(4), 304', doi='10.3390/rs9040304')

AP_1992 = Reference(
    key='ap1992', authors='Ap, J.', year=1992,
    title="Residents' perceptions on tourism impacts",
    container='Annals of Tourism Research, 19(4), 665–690', doi='10.1016/0160-7383(92)90060-3')

BUTLER_1980 = Reference(
    key='butler1980', authors='Butler, R. W.', year=1980,
    title='The concept of a tourist area cycle of evolution: implications for management of resources',
    container='Canadian Geographer, 24(1), 5–12', doi='10.1111/j.1541-0064.1980.tb00970.x')

WMO_2017 = Reference(
    key='wmo2017', authors='World Meteorological Organization', year=2017, entry_type='techreport',
    title='WMO Guidelines on the Calculation of Climate Normals', container='WMO-No. 1203',
    publisher='WMO, Geneva')

OPENDMO = Reference(
    key='opendmo2026', authors='OpenDMO contributors', year=2026, entry_type='misc',
    title='OpenDMO: Open Destination Management & Analytics Platform (v2.0) — methodology registry',
    url='https://github.com/ak7shuvo/OpenDMOA')

ALL_REFERENCES = [CIFUENTES_1992, UNWTO_2004, IRTS_2008, SACKS_2002, ARCHER_FLETCHER_1996, WINTERS_1960,
                  HOLT_2004, FPP3, HYNDMAN_KOEHLER_2006, SAATY_1980, AHMED_DEWAN_2017, AP_1992,
                  BUTLER_1980, WMO_2017, OPENDMO]
