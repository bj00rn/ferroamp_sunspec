from typing import TypedDict, Dict


class PhaseValues(TypedDict):
    """Phase Values Model for the Ferroamp Inverter from ExtApi.
    """
    L1: str
    L2: str
    L3: str


class FerroampData(TypedDict):
    """
    Ferroamp Data Model for the Ferroamp Inverter from ExtApi.
    This model represents the data structure for the Ferroamp inverter.
    """
    gridfreq: Dict[str, str]
    iace: PhaseValues
    iext: PhaseValues
    iextd: PhaseValues
    iextq: PhaseValues
    il: PhaseValues
    ild: PhaseValues
    iload: PhaseValues
    iloadd: PhaseValues
    iloadq: PhaseValues
    ilq: PhaseValues
    pbat: Dict[str, str]
    pext: PhaseValues
    pextreactive: PhaseValues
    pinv: PhaseValues
    pinvreactive: PhaseValues
    pload: PhaseValues
    ploadreactive: PhaseValues
    ppv: Dict[str, str]
    ratedcap: Dict[str, str]
    sext: Dict[str, str]
    soc: Dict[str, str]
    soh: Dict[str, str]
    state: Dict[str, str]
    ts: Dict[str, str]
    udc: Dict[str, str]
    ul: PhaseValues
    wbatcons: Dict[str, str]
    wbatprod: Dict[str, str]
    wextconsq: PhaseValues
    wextprodq: PhaseValues
    winvconsq: PhaseValues
    winvprodq: PhaseValues
    wloadconsq: PhaseValues
    wloadprodq: PhaseValues
    wpv: Dict[str, str]
