# noqa: D100

import logging
from typing import Optional, Union

import hail as hl
import json

from gnomad.resources.resource_utils import (
    DataException,
    GnomadPublicMatrixTableResource,
    GnomadPublicTableResource,
    VersionedMatrixTableResource,
    VersionedTableResource,
)
from gnomad.sample_qc.ancestry import POP_NAMES
from gnomad.utils.annotations import (
    get_gks,
    add_gks_va,
    add_gks_vrs,
    gks_compute_seqloc_digest,
)

logging.basicConfig(
    format="%(asctime)s (%(name)s %(lineno)s): %(message)s",
    datefmt="%m/%d/%Y %I:%M:%S %p",
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CURRENT_EXOME_RELEASE = ""
CURRENT_GENOME_RELEASE = "3.1.2"
CURRENT_GENOME_COVERAGE_RELEASE = "3.0.1"
EXOME_RELEASES = []
GENOME_RELEASES = ["3.0", "3.1", "3.1.1", "3.1.2"]
GENOME_COVERAGE_RELEASES = GENOME_RELEASES + ["3.0.1"]
DATA_TYPES = ["genomes"]
MAJOR_RELEASES = ["v3", "v4"]
CURRENT_MAJOR_RELEASE = MAJOR_RELEASES[-1]


GENOME_POPS = ["AFR", "AMI", "AMR", "ASJ", "EAS", "FIN", "NFE", "SAS", "OTH"]
SUBSETS = {
    "v3": [
        "non_v2",
        "non_topmed",
        "non_cancer",
        "controls_and_biobanks",
        "non_neuro",
        "tgp",
        "hgdp",
    ],
    "v4": ["ukb", "non_ukb", "non_topmed"],
}
"""
Order to sort subgroupings during VCF export by version.

Ensures that INFO labels in VCF are in desired order (e.g., tgp_raw_AC_esn_XX).
"""

GROUPS = ["adj", "raw"]
"""
Group names used to generate labels for high quality genotypes and all raw genotypes.

Used in VCF export.
"""

SEXES = ["XX", "XY"]
"""
Sample sexes used in VCF export.

Used to stratify frequency annotations (AC, AN, AF) for each sex.
"""

POPS = {
    "v3": ["afr", "ami", "amr", "asj", "eas", "fin", "nfe", "oth", "sas", "mid"],
    "v4": [
        "afr",
        "amr",
        "asj",
        "eas",
        "fin",
        "mid",
        "nfe",
        "remaining",
        "sas",
    ],
}
"""
Global ancestry groups in gnomAD by version.
"""

COHORTS_WITH_POP_STORED_AS_SUBPOP = ["tgp", "hgdp"]
"""
Subsets in gnomAD v3.1 that are broken down by their known subpops instead of global pops in the frequency struct.
"""

TGP_POPS = [
    "esn",
    "pur",
    "pjl",
    "clm",
    "jpt",
    "chb",
    "stu",
    "itu",
    "tsi",
    "mxl",
    "ceu",
    "msl",
    "yri",
    "beb",
    "fin",
    "khv",
    "cdx",
    "lwk",
    "acb",
    "asw",
    "ibs",
    "gbr",
    "pel",
    "gih",
    "chs",
    "gwd",
]
"""
1000 Genomes Project (1KG/TGP) subpops.
"""

HGDP_POPS = [
    "japanese",
    "papuan",
    "adygei",
    "orcadian",
    "biakapygmy",
    "yakut",
    "han",
    "uygur",
    "miaozu",
    "mongola",
    "balochi",
    "bedouin",
    "russian",
    "daur",
    "pima",
    "hezhen",
    "sindhi",
    "yizu",
    "oroqen",
    "san",
    "tuscan",
    "tu",
    "palestinian",
    "tujia",
    "druze",
    "pathan",
    "basque",
    "makrani",
    "italian",
    "naxi",
    "karitiana",
    "sardinian",
    "mbutipygmy",
    "mozabite",
    "yoruba",
    "lahu",
    "dai",
    "cambodian",
    "melanesian",
    "french",
    "brahui",
    "hazara",
    "bantusafrica",
    "surui",
    "mandenka",
    "kalash",
    "xibo",
    "colombian",
    "bantukenya",
    "she",
    "burusho",
    "maya",
]
"""
Human Genome Diversity Project (HGDP) subpops.
"""

TGP_POP_NAMES = {
    "chb": "Han Chinese",
    "jpt": "Japanese",
    "chs": "Southern Han Chinese",
    "cdx": "Chinese Dai",
    "khv": "Kinh",
    "ceu": "Utah Residents (European Ancestry)",
    "tsi": "Toscani",
    "fin": "Finnish",
    "gbr": "British",
    "ibs": "Iberian",
    "yri": "Yoruba",
    "lwk": "Luhya",
    "gwd": "Gambian",
    "msl": "Mende",
    "esn": "Esan",
    "asw": "African-American",
    "acb": "African Caribbean",
    "mxl": "Mexican-American",
    "pur": "Puerto Rican",
    "clm": "Colombian",
    "pel": "Peruvian",
    "gih": "Gujarati",
    "pjl": "Punjabi",
    "beb": "Bengali",
    "stu": "Sri Lankan Tamil",
    "itu": "Indian Telugu",
}
"""
1000 Genomes Project (1KG/TGP) pop label map.
"""

POPS_STORED_AS_SUBPOPS = TGP_POPS + HGDP_POPS
POPS_TO_REMOVE_FOR_POPMAX = {"asj", "fin", "oth", "ami", "mid", "remaining"}
"""
Populations that are removed before popmax calculations.
"""

DOWNSAMPLINGS = {
    "v3": [
        10,
        20,
        50,
        100,
        200,
        500,
        1000,
        2000,
        5000,
        10000,
        15000,
        20000,
        25000,
        30000,
        40000,
        50000,
        60000,
        70000,
        75000,
        80000,
        85000,
        90000,
        95000,
        100000,
        110000,
        120000,
    ],
    "v4": [
        10,
        100,
        500,
        1000,
        2000,
        5000,
        10000,
        20000,
        50000,
        100000,
        200000,
        500000,
    ],
}
"""
List of the downsampling numbers to use for frequency calculations by version.
"""

gnomad_syndip = VersionedMatrixTableResource(
    default_version="3.0",
    versions={
        "3.0": GnomadPublicMatrixTableResource(
            path="gs://gnomad-public-requester-pays/truth-sets/hail-0.2/gnomad_v3_syndip.b38.mt"
        )
    },
)

na12878 = VersionedMatrixTableResource(
    default_version="3.0",
    versions={
        "3.0": GnomadPublicMatrixTableResource(
            path="gs://gnomad-public-requester-pays/truth-sets/hail-0.2/gnomad_v3_na12878.mt"
        )
    },
)


def get_coverage_ht(coverage_ht, data_type, coverage_version):
    if coverage_ht == "auto":
        return hl.read_table(coverage(data_type).versions[coverage_version].path)
    elif type(coverage_ht) == hl.Table:
        return hl.read_table(coverage_ht)
    else:
        return None


def _public_release_ht_path(data_type: str, version: str) -> str:
    """
    Get public release table path.

    :param data_type: One of "exomes" or "genomes"
    :param version: One of the release versions of gnomAD on GRCh38
    :return: Path to release Table
    """
    version_prefix = "r" if version.startswith("3.0") else "v"
    return f"gs://gnomad-public-requester-pays/release/{version}/ht/{data_type}/gnomad.{data_type}.{version_prefix}{version}.sites.ht"


def _public_coverage_ht_path(data_type: str, version: str) -> str:
    """
    Get public coverage hail table.

    :param data_type: One of "exomes" or "genomes"
    :param version: One of the release versions of gnomAD on GRCh38
    :return: path to coverage Table
    """
    version_prefix = "r" if version.startswith("3.0") else "v"
    return f"gs://gnomad-public-requester-pays/release/{version}/coverage/{data_type}/gnomad.{data_type}.{version_prefix}{version}.coverage.ht"


def public_release(data_type: str) -> VersionedTableResource:
    """
    Retrieve publicly released versioned table resource.

    :param data_type: One of "exomes" or "genomes"
    :return: Release Table
    """
    if data_type not in DATA_TYPES:
        raise DataException(
            f"{data_type} not in {DATA_TYPES}, please select a data type from"
            f" {DATA_TYPES}"
        )

    if data_type == "exomes":
        current_release = CURRENT_EXOME_RELEASE
        releases = EXOME_RELEASES
    else:
        current_release = CURRENT_GENOME_RELEASE
        releases = GENOME_RELEASES

    return VersionedTableResource(
        current_release,
        {
            release: GnomadPublicTableResource(
                path=_public_release_ht_path(data_type, release)
            )
            for release in releases
        },
    )


def coverage(data_type: str) -> VersionedTableResource:
    """
    Retrieve gnomAD's coverage table by data_type.

    :param data_type: One of "exomes" or "genomes"
    :return: Coverage Table
    """
    if data_type not in DATA_TYPES:
        raise DataException(
            f"{data_type} not in {DATA_TYPES}, please select a data type from"
            f" {DATA_TYPES}"
        )

    if data_type == "exomes":
        current_release = CURRENT_EXOME_RELEASE
        releases = EXOME_RELEASES
    else:
        current_release = CURRENT_GENOME_COVERAGE_RELEASE
        releases = GENOME_COVERAGE_RELEASES

    return VersionedTableResource(
        current_release,
        {
            release: GnomadPublicTableResource(
                path=_public_coverage_ht_path(data_type, release)
            )
            for release in releases
        },
    )


def coverage_tsv_path(data_type: str, version: Optional[str] = None) -> str:
    """
    Retrieve gnomAD's coverage table by data_type.

    :param data_type: One of "exomes" or "genomes"
    :return: Coverage Table
    """
    if data_type not in DATA_TYPES:
        raise DataException(
            f"{data_type} not in {DATA_TYPES}, please select a data type from"
            f" {DATA_TYPES}"
        )

    if data_type == "exomes":
        if version is None:
            version = CURRENT_EXOME_RELEASE
        elif version not in EXOME_RELEASES:
            raise DataException(
                f"Version {version} of gnomAD exomes for GRCh38 does not exist"
            )
    else:
        if version is None:
            version = CURRENT_GENOME_COVERAGE_RELEASE
        elif version not in GENOME_COVERAGE_RELEASES:
            raise DataException(
                f"Version {version} of gnomAD genomes for GRCh38 does not exist"
            )

    version_prefix = "r" if version.startswith("3.0") else "v"
    return f"gs://gcp-public-data--gnomad/release/{version}/coverage/{data_type}/gnomad.{data_type}.{version_prefix}{version}.coverage.summary.tsv.bgz"


def release_vcf_path(data_type: str, version: str, contig: str) -> str:
    """
    Publically released VCF. Provide specific contig, i.e. "chr20", to retrieve contig specific VCF.

    :param data_type: One of "exomes" or "genomes"
    :param version: One of the release versions of gnomAD on GRCh37
    :param contig: Single contig "chr1" to "chrY"
    :return: Path to VCF
    """
    if version.startswith("2"):
        raise DataException(
            f"gnomAD version {version} is not available on reference genome GRCh38"
        )

    contig = f".{contig}" if contig else ""
    version_prefix = "r" if version.startswith("3.0") else "v"
    return f"gs://gcp-public-data--gnomad/release/{version}/vcf/{data_type}/gnomad.{data_type}.{version_prefix}{version}.sites{contig}.vcf.bgz"


def gnomad_gks(
    version: str,
    variant: str,
    data_type: str = "genomes",
    by_ancestry_group: bool = False,
    by_sex: bool = False,
    vrs_only: bool = False,
    ht: Union[str, hl.Table] = None,
    coverage_ht: Union[str, hl.Table] = "auto",
) -> dict:
    """
    Call get_gks() and return VRS information and frequency information for the specified gnomAD release version and variant.

    :param version: String of version of gnomAD release to use.
    :param variant: String of variant to search for (chromosome, position, ref, and alt, separated by '-'). Example for a variant in build GRCh38: "chr5-38258681-C-T".
    :param data_type: String of either "exomes" or "genomes" for the type of reads that are desired.
    :param by_ancestry_group: Boolean to pass to obtain frequency information for each ancestry group in the desired gnomAD version.
    :param by_sex: Boolean to pass if want to return frequency information for each ancestry group split by chromosomal sex.
    :param vrs_only: Boolean to pass if only want VRS information returned (will not include allele frequency information).
    :param ht: Path of Hail Table to parse if different from what the public_release() method would return for the version, or an existing hail.Table object.
    :param coverage_ht: Path of coverage_ht, an existing hail.Table object, or 'auto' to automatically lookup coverage ht.
    :return: Dictionary containing VRS information (and frequency information split by ancestry groups and sex if desired) for the specified variant.

    """
    # If ht is not already a table,
    # read in gnomAD release table to filter to chosen variant.
    if not isinstance(ht, hl.Table):
        if ht:
            ht = hl.read_table(ht)
        else:
            ht = hl.read_table(public_release(data_type).versions[version].path)

    high_level_version = f"v{version.split('.')[0]}"

    # Read coverage statistics.

    if high_level_version == "v3":
        coverage_version = "3.0.1"
    else:
        raise NotImplementedError(
            "gnomad_gks() is currently only implemented for gnomAD v3."
        )

    coverage_ht = get_coverage_ht(coverage_ht, data_type, coverage_version)

    # Retrieve ancestry groups from the imported POPS dictionary.
    pops_list = list(POPS[high_level_version]) if by_ancestry_group else None

    # Throw warnings if contradictory arguments passed.
    if by_ancestry_group and vrs_only:
        logger.warning(
            "Both 'vrs_only' and 'by_ancestry_groups' have been specified. Ignoring"
            " 'by_ancestry_groups' list and returning only VRS information."
        )
    elif by_sex and not by_ancestry_group:
        logger.warning(
            "Splitting whole database by sex is not yet supported. If using 'by_sex',"
            " please also specify 'by_ancestry_group' to stratify by."
        )

    # Call and return get_gks() for chosen arguments.
    gks_info = get_gks(
        ht=ht,
        variant=variant,
        label_name="gnomAD",
        label_version=version,
        coverage_ht=coverage_ht,
        ancestry_groups=pops_list,
        ancestry_groups_dict=POP_NAMES,
        by_sex=by_sex,
        vrs_only=vrs_only,
    )

    return gks_info


# VRS Annotation needs to be done separately. It needs to compute the sequence location
# digest and this cannot be done in hail. It needs to export the record to JSON, compute
# sequence location digests in python, and then that can be imported to a hail table.
def gnomad_gks_batch(
    ht: hl.Table,
    locus_interval: hl.IntervalExpression,
    version: str,
    data_type: str = "genomes",
    by_ancestry_group: bool = False,
    by_sex: bool = False,
    vrs_only: bool = False,
    coverage_ht: Union[str, hl.Table] = "auto",
):
    """
    Performs gnomad GKS annotations on a range of variants at once.

    :param ht: Path of Hail Table to parse if different from what the public_release() method would return for the version, or an existing hail.Table object.
    :param locus_interval: Hail IntervalExpression of locus<reference_genome>. e.g. hl.locus_interval('chr1', 1, 50000000, reference_genome="GRCh38")
    :param version: String of version of gnomAD release to use.
    :param data_type: String of either "exomes" or "genomes" for the type of reads that are desired.
    :param by_ancestry_group: Boolean to pass to obtain frequency information for each ancestry group in the desired gnomAD version.
    :param by_sex: Boolean to pass if want to return frequency information for each ancestry group split by chromosomal sex.
    :param vrs_only: Boolean to pass if only want VRS information returned (will not include allele frequency information).
    :param coverage_ht: Path of coverage_ht, an existing hail.Table object, or 'auto' to automatically lookup coverage ht.
    :return: Dictionary containing VRS information (and frequency information split by ancestry groups and sex if desired) for the specified variant.
    """
    # If ht is not already a table,
    # read in gnomAD release table to filter to chosen variant.
    if not isinstance(ht, hl.Table):
        if ht:
            ht = hl.read_table(ht)
        else:
            ht = hl.read_table(public_release(data_type).versions[version].path)

    high_level_version = f"v{version.split('.')[0]}"

    # Read coverage statistics.

    if high_level_version == "v3":
        coverage_version = "3.0.1"
    else:
        raise NotImplementedError(
            "gnomad_gks() is currently only implemented for gnomAD v3."
        )

    coverage_ht = get_coverage_ht(coverage_ht, data_type, coverage_version)

    # Retrieve ancestry groups from the imported POPS dictionary.
    pops_list = list(POPS[high_level_version]) if by_ancestry_group else None

    # Throw warnings if contradictory arguments passed.
    if by_ancestry_group and vrs_only:
        logger.warning(
            "Both 'vrs_only' and 'by_ancestry_groups' have been specified. Ignoring"
            " 'by_ancestry_groups' list and returning only VRS information."
        )
    elif by_sex and not by_ancestry_group:
        logger.warning(
            "Splitting whole database by sex is not yet supported. If using 'by_sex',"
            " please also specify 'by_ancestry_group' to stratify by."
        )

    # Call and return get_gks*() for chosen arguments.
    # get_gks_va returns the table annotated with .gks_va_freq_dict
    # get_gks_va does not fill in the the .focusAllele value of .gks_va_freq_dict
    # this is the vrs variant and is mostly just based on the values in the variant and info column,
    # but it also needs to compute the SequenceLocation digest, which cannot be done in hail

    # Add .vrs and .vrs_json (the JSON string representation of .vrs)
    # Omits .location._id
    ht_with_vrs = add_gks_vrs(ht)
    # Add .gks_va_freq_dict
    ht_with_va = add_gks_va(
        ht=ht_with_vrs,
        label_name="gnomAD",
        label_version=version,
        coverage_ht=coverage_ht,
        ancestry_groups=pops_list,
        ancestry_groups_dict=POP_NAMES,
        by_sex=by_sex,
        vrs_only=vrs_only,
    )
    filtered = hl.filter_intervals(ht_with_va, [locus_interval])
    annotations = filtered.select(
        gks_va_freq_dict=hl.json(filtered.gks_va_freq_dict), vrs_json=filtered.vrs_json
    ).collect()  # might be big

    outputs = []
    for ann in annotations:
        vrs_json = ann.vrs_json
        vrs_variant = json.loads(vrs_json)
        # begin filling in fields ommitted by add_gks_vrs and add_gks_va
        vrs_variant = gks_compute_seqloc_digest(vrs_variant)
        va_freq_dict = json.loads(ann.gks_va_freq_dict)  # Hail Struct as json
        va_freq_dict["focusAllele"] = vrs_variant

        locus = {
            "contig": ann.locus.contig,
            "position": ann.locus.position,
            "reference_genome": ann.locus.reference_genome.name,
        }

        outputs.append(
            {
                "locus": locus,
                "alleles": ann.alleles,
                "gks_va_freq": va_freq_dict,
                "gks_vrs_variant": vrs_variant,
            }
        )

    return outputs
