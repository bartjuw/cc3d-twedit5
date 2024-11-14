from dataclasses import dataclass, field
from typing import Optional, List
import pandas as pd
from cc3d.twedit5.Plugins.CC3DGUIDesign.helpers.module_data import ModuleData
from cc3d.twedit5.Plugins.CC3DGUIDesign.helpers.xml_parse_data import XMLParseData, ParseMode
from cc3d.core.XMLUtils import dictionaryToMapStrStr as d2mss
from cc3d.core.XMLUtils import ElementCC3D, CC3DXMLListPy
from collections import OrderedDict


@dataclass
class VolumePluginData(XMLParseData):
    global_params: ModuleData = None
    by_type_params: ModuleData = None
    # mode: str = ''  # global, by_type, by_cell,
    by_type_types: List = field(default_factory=lambda: [str, float, float])
    by_type_cols: List[str] = field(default_factory=lambda:  ['CellType', 'TargetVolume', 'LambdaVolume'])
    by_type_editable_cols: List[str] = field(default_factory=lambda: ['TargetVolume', 'LambdaVolume'])

    def get_default_global_params(self):
        cols = ['TargetVolume', 'LambdaVolume']
        return ModuleData(df=pd.DataFrame([[0., 0.]], columns=cols),
                   types=[float, float], editable_columns=cols)

    def get_default_by_type_params(self, cell_types):
        cols = ['CellType', 'TargetVolume', 'LambdaVolume']
        data = []
        for cell_type in cell_types:
            if cell_type.lower() == 'medium':
                continue
            data.append([cell_type, 0., 0.])
        return ModuleData(df=pd.DataFrame(data=data, columns=self.by_type_cols),
                   types=self.by_type_types, editable_columns=self.by_type_editable_cols)

    def parse_xml(self, root_element):
        sim_dicts = {}
        plugin_element = root_element.getFirstElement('Plugin', d2mss({'Name': 'Volume'}))
        if plugin_element is None:
            return sim_dicts

        if plugin_element.findElement('TargetVolume') and plugin_element.findElement('LambdaVolume'):
            target_volume = plugin_element.getFirstElement('TargetVolume').getDouble()
            lambda_volume = plugin_element.getFirstElement('LambdaVolume').getDouble()

            module_data = ModuleData(
                df=pd.DataFrame(data=[[target_volume, lambda_volume]], columns=['TargetVolume', 'LambdaVolume']),
                types=[float, float],
                editable_columns=['TargetVolume', 'LambdaVolume']

            )
            self.mode = ParseMode.GLOBAL
            self.global_params = module_data
        elif plugin_element.findElement('VolumeEnergyParameters'):
            plugin_elements = CC3DXMLListPy(plugin_element.getElements('VolumeEnergyParameters'))
            data = []
            for plugin_element in plugin_elements:
                target_volume = float(plugin_element.getAttribute('TargetVolume'))
                lambda_volume = float(plugin_element.getAttribute('LambdaVolume'))
                cell_type = plugin_element.getAttribute('CellType')
                data.append([cell_type, target_volume, lambda_volume])

            cols = ['CellType', 'TargetVolume', 'LambdaVolume']
            module_data = ModuleData(
                df=pd.DataFrame(data=data, columns=cols),
                types=[str, float, float],
                editable_columns=cols[1:]
            )
            self.mode = ParseMode.BY_TYPE
            self.by_type_params = module_data

        else:
            self.mode = ParseMode.BY_TYPE

    def generate_xml_element(self) -> Optional[ElementCC3D]:
        """
        Abstract fcn - reimplement XML Element in derived class
        """
        element = self.get_tool_element()

        gp = self.global_params
        btp = self.by_type_params

        if self.mode == ParseMode.GLOBAL:
            element.ElementCC3D('TargetVolume', {}, gp.df['TargetVolume'].values[0])
            element.ElementCC3D('LambdaVolume', {}, gp.df['LambdaVolume'].values[0])
        elif self.mode == ParseMode.BY_TYPE:
            for i, row in btp.df.iterrows():
                attrs = OrderedDict()
                attrs['CellType'] = row.CellType
                attrs['TargetVolume'] = row.TargetVolume
                attrs['LambdaVolume'] = row.LambdaVolume
                element.ElementCC3D('VolumeEnergyParameters', attrs)

        return element

    def get_tool_element(self):
        """
        Returns base tool CC3D element
        :return:
        """
        return ElementCC3D('Plugin', {'Name': 'Volume'})

    def update_from_dependent_modules(self, dependent_module_data_dict):

        if dependent_module_data_dict is None:
            return
        cell_type_plugin_data = dependent_module_data_dict.get('CellType', None)

        if cell_type_plugin_data is None:
            return

        if self.mode != ParseMode.BY_TYPE:
            return

        if self.by_type_params.df is None:
            return

        cell_types = cell_type_plugin_data.get_cell_types()

        keep_mask = self.by_type_params.df['CellType'].isin(cell_types)

        self.by_type_params.df = self.by_type_params.df[keep_mask]

        # additional types
        additional_types = list(set(cell_types) - set(self.by_type_params.df['CellType']))

        data = []
        for cell_type in additional_types:
            if cell_type.lower() == 'medium':
                continue
            data.append([cell_type, 0., 0.])
        additional_df = pd.DataFrame(data=data, columns=self.by_type_cols)
        self.by_type_params.df = pd.concat([self.by_type_params.df, additional_df])
